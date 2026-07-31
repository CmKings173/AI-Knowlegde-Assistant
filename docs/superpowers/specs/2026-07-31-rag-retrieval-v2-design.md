# Thiết kế Retrieval RAG V2

Ngày: 2026-07-31

## Trạng thái

Thiết kế đã được thống nhất trong quá trình thảo luận. Tài liệu này là nguồn sự
thật cho quá trình triển khai và phải được người dùng duyệt trước khi bắt đầu sửa
code.

## Vấn đề

Luồng RAG hiện tại có thể tìm được chunk đúng nhưng vẫn đưa các chunk không liên
quan vào context cuối. Sau đó hệ thống chấp nhận câu trả lời nếu citation ID hợp
lệ về cú pháp, ngay cả khi nguồn được dẫn không hỗ trợ cho kết luận của LLM.

Các nguyên nhân mang tính hệ thống:

- Điểm hợp nhất thứ hạng RRF đang bị sử dụng như điểm tin cậy về độ liên quan.
- Context cuối được tạo bằng cách lấy một số lượng chunk cố định đứng đầu.
- Điểm dense và BM25 gốc không được giữ lại để phục vụ bước chọn context.
- Routing và evidence gate phụ thuộc vào danh sách keyword ngày càng dài.
- Metadata do ingestion tạo có thể sai nên không an toàn nếu dùng làm hard filter
  suy luận tự động.
- Citation validator chỉ kiểm tra source ID, chưa chứng minh context được chọn đủ
  sạch để làm căn cứ trả lời.
- Phần lớn test hiện tại dùng retriever giả và chưa chứng minh chất lượng
  end-to-end trên tài liệu đã được index thực tế.

Commit `4721cf0` là baseline ổn định đã được xác nhận. Commit `4ac2f57` và các thử
nghiệm tiếp theo được bảo toàn để tham khảo nhưng không được dùng làm nền cho V2.

## Mục tiêu

- Khôi phục baseline ổn định mà không viết lại lịch sử Git.
- Tăng độ chính xác của retrieval và context cuối với các cách diễn đạt tiếng Việt
  chưa từng gặp.
- Chỉ sử dụng một LLM hội thoại: Qwen chạy qua Ollama.
- Luồng thông thường chỉ gọi Qwen một lần để sinh câu trả lời.
- Chỉ cho phép gọi chính Qwen để rewrite khi retrieval ban đầu thực sự yếu hoặc
  lẫn nhiều chủ đề.
- Tiếp tục sử dụng embedding, BM25 và Qdrant.
- Trả lời một phần khi tài liệu chỉ hỗ trợ một phần câu hỏi.
- Phân biệt rõ các trạng thái lỗi và quan sát được lỗi phát sinh ở tầng nào.
- Chứng minh V2 tốt hơn bằng bộ evaluation end-to-end được lưu trong Git.

## Ngoài phạm vi

- Không dùng model planner riêng.
- Không dùng reranker model hoặc Infinity trong V2.
- Không dùng model verifier riêng.
- Không thêm Redis hoặc database mới.
- Không vá keyword riêng cho từng câu hỏi được báo lỗi.
- Không tuyên bố có thể trả lời đúng mọi input có thể tồn tại.
- Không thực hiện CI/CD trong phạm vi này.

## Phục hồi Git

Trạng thái thử nghiệm hiện tại được bảo toàn tại:

```text
archive-rag-experiments-e931279
```

Regression trên remote được revert mà không force-push:

```text
origin/main: 4ac2f57
└── hotfix-restore-rag-baseline
    └── 42433c7 Revert "Harden RAG evidence gating and add optional reranker"
```

V2 được phát triển từ source đã phục hồi trên branch:

```text
feature-rag-retrieval-v2
```

Hotfix và feature branch phải được review, kiểm thử độc lập trước khi merge. Các
fix hoặc feature tiếp theo không được commit trực tiếp lên `main`.

## Kiến trúc

```text
User query + lịch sử hội thoại giới hạn + document scope tường minh
→ Chuẩn hóa query
→ Áp dụng hard filter về quyền, tài liệu và phiên bản
→ Dense search + BM25 lần đầu
→ Hợp nhất candidate bằng RRF
→ Đánh giá chất lượng candidate
   ├── Evidence nhất quán: tiếp tục
   └── Evidence yếu hoặc lẫn domain:
       → Qwen rewrite query theo JSON schema
       → Retrieval lần hai
→ Chọn evidence và xây context
→ Qwen sinh câu trả lời grounded
→ Kiểm tra response và citation bằng logic deterministic
→ API trả câu trả lời, nguồn và ảnh liên quan
```

### Hợp đồng sử dụng model

Qwen là LLM hội thoại duy nhất. Hệ thống vẫn cần embedding provider để tìm kiếm
vector, nhưng embedding provider không phải model hội thoại hoặc planner.

Luồng thông thường gọi Qwen một lần. Luồng adaptive có thể gọi cùng Qwen một lần
để tạo rewrite ngắn và một lần để sinh câu trả lời. Nếu rewrite lỗi, hệ thống
fallback về kết quả retrieval của query gốc.

## Routing

Deterministic routing chỉ giữ những fast path an toàn:

- Input rỗng.
- Lời chào rõ ràng.
- Yêu cầu xem tiếp rõ ràng.
- `document_scope="selected"` nhưng không có tài liệu được chọn.

Các input khác phải ưu tiên thử retrieval trước khi kết luận không có thông tin
hoặc ngoài phạm vi. Retrieval không được phụ thuộc vào danh sách cụm từ HR, IT hay
policy tăng mãi theo từng lỗi.

Lịch sử hội thoại có thể được dùng để xác định đối tượng của câu hỏi tiếp nối,
nhưng không bao giờ được coi là evidence. Chỉ context lấy từ tài liệu mới được
dùng để hỗ trợ thông tin nghiệp vụ.

## Retrieval

### Tạo candidate

Mỗi lượt retrieval thực hiện:

1. Áp dụng hard filter.
2. Embed search query.
3. Dense search trong Qdrant.
4. Lexical search bằng BM25.
5. Hợp nhất danh sách candidate bằng RRF.

RRF chỉ là cơ chế hợp nhất thứ hạng candidate. Điểm RRF không được coi là
semantic confidence.

Mỗi candidate phải giữ lại đầy đủ nguồn gốc retrieval:

```json
{
  "dense_score": 0.82,
  "dense_rank": 1,
  "bm25_score": 4.12,
  "bm25_rank": 3,
  "rrf_score": 0.031,
  "matched_queries": ["original"],
  "document_id": "doc-id",
  "domain": "HR_POLICY",
  "section": "đường dẫn section"
}
```

Nếu candidate không xuất hiện trong dense hoặc BM25 thì phải ghi nhận rõ là
không có tín hiệu đó, không tự tạo điểm giả.

### Hard metadata và soft metadata

Hard filter chỉ gồm:

- Document ID do người dùng chọn tường minh.
- Phạm vi quyền truy cập.
- Phiên bản tài liệu hiện hành đã publish.
- Trạng thái tài liệu sẵn sàng retrieval.

Domain và knowledge type do hệ thống suy luận chỉ là tín hiệu phục vụ xếp hạng.
Chúng không được loại hoàn toàn candidate global vì metadata ingestion có thể sai.

### Đánh giá chất lượng candidate

Chất lượng được đánh giá từ nhiều tín hiệu đã hiệu chỉnh, không dựa vào một
ngưỡng RRF tùy ý:

- Raw dense similarity.
- Lexical evidence đã chuẩn hóa.
- Mức đồng thuận giữa dense và BM25.
- Khoảng cách điểm giữa các candidate.
- Mức tập trung hoặc phân tán giữa các document/domain.
- Tỷ lệ nội dung trùng lặp.

Các ngưỡng phải được hiệu chỉnh bằng bộ evaluation có version trong Git. Kết quả
yếu hoặc không nhất quán sẽ kích hoạt adaptive rewrite, không được lập tức trả
`insufficient_context`.

### Adaptive rewrite

Khi retrieval ban đầu yếu hoặc không nhất quán, Qwen chỉ nhận:

- User query hiện tại.
- Lịch sử giới hạn nếu đây là follow-up.
- JSON schema nghiêm ngặt dành cho rewrite.

Qwen không được trả lời câu hỏi hoặc tạo fact. Query gốc luôn được giữ lại và
rewrite chỉ được bổ sung tối đa hai search query ngắn. Retrieval lần hai hợp nhất
candidate của query gốc và các query rewrite.

## Chọn evidence

Context cuối không được tiếp tục dùng `retrieval.chunks[:N]`.

Evidence selector phải:

- Loại candidate dưới ngưỡng chất lượng đã hiệu chỉnh.
- Tránh chunk khác domain khi đã có evidence cùng domain nhất quán.
- Loại nội dung trùng lặp đáng kể.
- Ưu tiên bao phủ các section liên quan khác nhau.
- Giữ đúng document scope người dùng đã chọn.
- Chỉ mở rộng cấu trúc trong cùng tài liệu khi giúp tăng độ phủ evidence.
- Đưa evidence mạnh lên vị trí dễ chú ý, không chôn thông tin quan trọng.
- Áp dụng token budget sau khi chọn evidence.

Selector có thể trả ít hơn `FINAL_CONTEXT_TOP_N`. Đây là giới hạn tối đa, không
phải số lượng chunk bắt buộc phải lấy.

## Sinh câu trả lời

Qwen nhận:

1. System prompt.
2. Context giới hạn, có gắn source ID.
3. User query.
4. Lịch sử giới hạn nếu cần hiểu follow-up.

Quy tắc sinh:

- Chỉ dùng context làm evidence nghiệp vụ.
- Mọi kết luận nghiệp vụ quan trọng phải có citation.
- Không tự suy ra mức phạt, chính sách, IP, port, tài khoản hoặc bước thực hiện
  không có trong nguồn.
- Trả `partial` khi evidence chỉ hỗ trợ một phần yêu cầu.
- Chỉ trả `insufficient_context` khi không có evidence cốt lõi.
- Trả lời tiếng Việt có dấu, ngắn gọn và đúng trọng tâm.

Chỉ retry một lần nếu structured output sai định dạng hoặc sinh ngôn ngữ không
được phép.

## Validation và trạng thái

Fact guard heuristic tiếp tục bị tắt và không được đưa trở lại V2.

Deterministic validator chỉ kiểm tra những điều có thể chứng minh chắc chắn:

- Response là JSON hợp lệ theo schema.
- Status nằm trong danh sách cho phép.
- `SOURCE_n` thực sự tồn tại trong context.
- Citation inline và danh sách source khớp chính xác.
- Giá trị literal quan trọng như thời gian, IP và port có trong evidence được cite.

Validator không được giả vờ thực hiện semantic entailment tổng quát.

Các trạng thái phải được phân biệt:

- `answered`: evidence hỗ trợ thông tin cốt lõi được hỏi.
- `partial`: evidence chỉ hỗ trợ một phần.
- `insufficient_context`: retrieval không có evidence cốt lõi sử dụng được.
- `conflict`: các nguồn được retrieve mâu thuẫn.
- `generation_failed`: output của Qwen vẫn không sử dụng được sau retry.
- Lỗi hoặc degraded dependency phải được báo riêng, không được giả thành thiếu
  tài liệu.

## Xử lý lỗi

- Rewrite timeout hoặc sai định dạng: dùng candidate từ query gốc.
- Qdrant không hoạt động: trả dependency error, không để Qwen trả lời theo trí nhớ.
- BM25 không hoạt động: có thể degraded về dense-only nhưng phải log rõ.
- Qwen timeout hoặc lỗi: trả `generation_failed`.
- Không có candidate sử dụng được: trả thông báo thiếu context nhẹ nhàng.
- Dependency tùy chọn trong tương lai phải fail-open hoặc tiếp tục bị tắt.

## Observability

Trace của mỗi request phải chỉ ra được tầng gây lỗi:

- Route và lý do dùng fast path.
- Query gốc và query rewrite.
- Dense/BM25 rank và score.
- RRF score cùng nguồn gốc retrieval.
- Quyết định đánh giá chất lượng và lý do.
- Chunk được chọn, chunk bị loại và lý do tương ứng.
- Số token context.
- Số lần gọi generation và latency.
- Status cuối và citation ID.

Log không được chứa secret hoặc toàn bộ nội dung tài liệu nhạy cảm.

## Evaluation

Bộ evaluation phải được version hóa trong repo, không chỉ nằm dưới thư mục
runtime `data/` đang bị Git ignore.

Các nhóm test:

- Câu hỏi fact chính xác.
- Paraphrase và cách nói tiếng Việt đời thường.
- Lỗi chính tả nhẹ.
- Câu hỏi về hậu quả.
- Câu hỏi quy trình.
- Câu hỏi liệt kê hoặc tổng hợp.
- Câu hỏi nhiều ý.
- Follow-up phụ thuộc lịch sử.
- Câu chỉ trả lời được một phần.
- Câu nội bộ nhưng tài liệu không có thông tin.
- Hội thoại rõ ràng ngoài phạm vi.
- Candidate nhiễu khác domain.
- Lọc theo tài liệu được chọn.
- Tài liệu mới được ingestion.

Các câu regression đại diện cho nhóm hành vi, không được biến thành keyword rule.
Phải có ít nhất một holdout set không được dùng khi điều chỉnh threshold.

Các chỉ số bắt buộc:

- Recall@K và MRR.
- Tỷ lệ tìm đúng section.
- Độ chính xác của final context.
- Tỷ lệ context sai domain.
- Citation trỏ đúng section.
- Độ chính xác của `answered`, `partial` và refusal.
- Số critical fact không có nguồn hỗ trợ.
- Phân vị latency của normal path và adaptive path.

Quality gate ban đầu:

- Recall@5 trên câu có đáp án đạt ít nhất 90% và không thấp hơn baseline
  `4721cf0`.
- Citation đúng section đạt ít nhất 95% trên tập đã review.
- Không chấp nhận critical literal không có trong nguồn.
- Loại chunk sai domain khỏi final context khi đã có evidence đúng và nhất quán.
- P95 normal path không tăng quá 20% so với baseline đã đo.
- Unit test, integration test, ingestion test và frontend check đều pass.

Nếu một quality gate không thể đạt với corpus hoặc model hiện tại, phải báo cáo
kết quả và xem lại thiết kế. Không được tự ý hạ tiêu chuẩn để cho test pass.

## Các lát cắt triển khai

1. Bảo toàn và xác minh baseline ổn định.
2. Thêm evaluation cases vào Git và đo baseline.
3. Giữ raw retrieval provenance qua bước fusion.
4. Thêm candidate quality assessment và evidence selector.
5. Chuyển routing mơ hồ/domain sang retrieval-first.
6. Thêm adaptive rewrite bằng chính Qwen.
7. Phân biệt failure status và siết deterministic validation.
8. Chạy test tập trung, full test, evaluation và manual smoke test.
9. Code review và chỉ push feature branch đã được review.

Mỗi lát cắt phải bắt đầu bằng test hoặc evaluation case đang fail và được commit
thành một thay đổi nhất quán.

## Rủi ro và biện pháp kiểm soát

- **Adaptive path tăng latency:** chỉ kích hoạt khi retrieval yếu theo ngưỡng đã
  hiệu chỉnh và đo riêng normal/adaptive path.
- **Rewrite tự tạo nội dung:** dùng schema nghiêm ngặt, không cho trả fact, giữ
  query gốc, tối đa hai rewrite và có fallback.
- **Metadata gây false negative:** metadata suy luận không bao giờ là hard filter.
- **Context bị lọc quá mạnh:** hiệu chỉnh bằng holdout và luôn bảo toàn evidence
  mạnh nhất từ query gốc.
- **Qwen vẫn suy diễn semantic không có nguồn:** dùng context sạch, prompt nghiêm,
  kiểm tra literal, đo citation và ưu tiên `partial`; không tuyên bố có semantic
  verifier hoàn chỉnh.
- **Overfit evaluation:** kiểm tra đủ nhóm hành vi và có holdout.
- **Regression vận hành:** giữ baseline và V2 có thể deploy độc lập cho đến khi
  V2 vượt qua toàn bộ quality gate.

## Definition of Done

- Baseline ổn định có thể phục hồi và lịch sử thử nghiệm vẫn được bảo toàn.
- V2 được triển khai trên feature branch mà không cần planner/reranker model riêng.
- Query thông thường chỉ dùng một lần Qwen generation.
- Retrieval yếu có thể adaptive rewrite bằng cùng Qwen.
- Final context được chọn theo chất lượng evidence thay vì cắt top-N cố định.
- Failure status xác định đúng lỗi retrieval, dependency hoặc generation.
- Evaluation và toàn bộ kiểm tra của repo vượt qua các quality gate đã ghi.
- Regression đã báo và các nhóm holdout chưa từng dùng được kiểm chứng end-to-end.
- Feature branch đã review, sẵn sàng merge mà không force-push `main`.
