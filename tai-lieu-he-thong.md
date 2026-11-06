# Hệ cơ sở tri thức giải bài tập hoá vô cơ THCS

## 1. Mở đầu

Bài toán đặt ra là xây dựng một hệ cơ sở tri thức cho phần hoá vô cơ cơ bản ở bậc trung học cơ sở. Hệ thống nhận đề có cấu trúc, suy ra lời giải từ luật đang lưu, rồi trình bày lại bằng lời tiếng Việt theo cách một bài giải trên lớp vẫn được viết.

Ba yêu cầu chi phối toàn bộ thiết kế:

- Đáp án phải được suy ra. Hệ thống không lưu sẵn phương trình đã cân bằng, không lưu sẵn chuỗi điều chế, và không lưu sẵn kết quả tính của từng bài.
- Mỗi kết luận đều truy được về một luật: bảo toàn nguyên tố, một luật phản ứng theo lớp chất, hoặc một công thức lượng chất.
- Lời giải đưa ra cho người đọc là một đoạn văn có mở, có các bước và có câu chốt, trong khi máy vẫn giữ bản kết quả có cấu trúc để kiểm tra.

Phạm vi chất và phản ứng bám chương trình THCS cơ bản. Bảng tuần hoàn được lưu đủ 118 nguyên tố để có khối lượng nguyên tử và loại nguyên tố, còn các phản ứng chỉ chạy trên 110 hợp chất lõi.

## 2. Bài toán cần giải

Hệ thống giải ba dạng.

**Dạng 1, cân bằng phương trình.** Đầu vào là một sơ đồ chưa có hệ số. Đầu ra là phương trình với hệ số nguyên dương nhỏ nhất sao cho mọi nguyên tố có số nguyên tử hai vế bằng nhau. Dạng này chỉ xét bảo toàn nguyên tử. Việc phản ứng có xảy ra trong phòng thí nghiệm thuộc dạng 2.

**Dạng 2, chuỗi điều chế.** Đầu vào là chất đầu và chất đích. Hệ thống tìm chuỗi phản ứng ngắn nhất, dài tối đa 5 bước. Có hai chế độ thuốc thử: dùng mọi chất trong phạm vi đã học, hoặc chỉ dùng danh sách chất cho trước. Chuỗi là một dòng chuyển hoá. Mỗi bước truy một chất trung gian; các chất còn lại lấy từ tủ thuốc thử. Chất sinh ra ở bước trước được dùng cho bước sau.

**Dạng 3, tính lượng chất.** Đầu vào là các đại lượng đã biết và một đại lượng cần tìm. Đại lượng gồm khối lượng, số mol, thể tích khí ở điều kiện tiêu chuẩn, nồng độ mol và thể tích dung dịch. Thể tích mol của khí lấy Vm = 22,4 lít/mol.

Đầu vào là bản ghi có trường, ví dụ công thức, chế độ thuốc thử, danh sách dữ kiện. Hệ thống không đọc một câu đề tiếng Việt tự do.

## 3. Khung mô hình

Mô hình gồm bốn thành phần khái niệm và ba lớp luật, cộng thêm một lớp mẫu câu dùng riêng cho việc viết lời giải.

```text
Nguyên tố E ──┐
Hợp chất C ───┼──► R1 ràng buộc ──► chất đã được xếp lớp và gắn độ tan
Điều kiện Cond┘         │
                        ▼
                 R2 luật phản ứng theo lớp
                        │
                        ▼
              phản ứng cụ thể vừa được sinh và cân bằng
                        │
           ┌────────────┼────────────┐
           ▼            ▼            ▼
     Dạng 1         Dạng 2         Dạng 3
     bảo toàn       suy diễn lùi   suy diễn tiến
     nguyên tố      tìm chuỗi      trên công thức R3
           └────────────┼────────────┘
                        ▼
              vết các bước đã dùng
                        ▼
              mẫu câu + chỗ trống
                        ▼
              lời giải tiếng Việt
```

Khi nạp tri thức, máy tự đọc công thức, tự tính thành phần nguyên tố, tự xếp lớp và tự tính độ tan. Bản ghi lưu sẵn phải khớp với kết quả vừa suy ra. Nếu lệch, bản ghi bị từ chối và dữ liệu cũ được giữ nguyên. Nhờ vậy lớp chất và độ tan là hệ quả của R1, không phải nhãn ghi tay rồi để máy tin theo.

### 3.1. Nguyên tố

Mỗi nguyên tố mang cùng một lược đồ: ký hiệu, tên, số hiệu nguyên tử, chu kỳ, nhóm bảng tuần hoàn, khối, họ (để trống hoặc họ lantan), khối lượng nguyên tử, các hoá trị, loại kim loại hoặc phi kim, thứ tự hoạt động hoá học, và các nhóm tính chất.

Nhóm tính chất dùng trong luật là kiềm, kiềm thổ, halogen và lưỡng tính. Nhóm này khác với cột của bảng tuần hoàn. Thứ tự hoạt động là một số nguyên: số nhỏ hơn nghĩa là hoạt động hơn. Dãy đang dùng là K, Ba, Ca, Na, Mg, Al, Zn, Fe, Ni, Sn, Pb, H, Cu, Hg, Ag, Pt, Au, với hiđro mang số 12 để so sánh kim loại đứng trước hay đứng sau hiđro. Nguyên tố không nằm trong dãy thì để trống thứ tự hoạt động.

Khối lượng dùng khi tính và khi chấm: H = 1, C = 12, N = 14, O = 16, Na = 23, Mg = 24, Al = 27, Si = 28, P = 31, S = 32, Cl = 35,5, K = 39, Ca = 40, Fe = 56, Cu = 64, Zn = 65, Ag = 108, Ba = 137.

### 3.2. Hợp chất

Mỗi hợp chất có công thức, tên, lớp, nhãn lớp, thành phần nguyên tố, và trạng thái khí, lỏng, rắn hoặc dung dịch. Thành phần là mảng các cặp nguyên tố và số nguyên tử, đúng theo công thức, kể cả công thức có ngoặc như Ca(OH)2 và công thức có NH4 viết liền.

Ion không được lưu thành một chất riêng. Cation và anion chỉ được tách lúc chạy, từ công thức và bảng anion của R1.

Bộ hợp chất lõi có 110 chất: 55 muối trung hoà, 10 kim loại, 10 bazơ, 8 phi kim, 8 oxit bazơ, 6 axit, 5 oxit axit, 2 oxit trung tính, 2 oxit lưỡng tính, 2 muối axit, 1 oxit hỗn hợp và amoniac. Nước là oxit trung tính, trạng thái lỏng. Amoniac là chất khí, có lớp riêng, không bị xếp vào bazơ tan. Fe3O4 là oxit hỗn hợp vì sắt có hai hoá trị trong cùng một công thức.

### 3.3. Điều kiện phản ứng

Điều kiện là một khái niệm độc lập, ngang hàng với nguyên tố và hợp chất. Mỗi điều kiện có mã, tên, ký hiệu in trên mũi tên và mô tả. Từ điển có 13 điều kiện: đun nóng, loãng, đặc, đặc và đun, loãng và đun, xúc tác, đun và xúc tác, ánh sáng, đun và ánh sáng, áp suất, đun và áp suất, điện phân nóng chảy, điện phân dung dịch.

Không có mã “không điều kiện”. Luật nào không cần điều kiện thì để danh sách điều kiện rỗng. Luật hiện đang dùng đun nóng, loãng, đặc và đun, đun kèm xúc tác, và điện phân nóng chảy. Các điều kiện còn lại nằm trong từ điển để mở rộng.

### 3.4. Luật R1: ràng buộc và phân loại

R1 gồm cây lớp, vài ngoại lệ phân loại, bảng anion và bảng độ tan.

Cây lớp có 15 nút. Mỗi lớp có một tên và danh sách lớp con. Một lớp chỉ có một cha, và không có vòng.

```text
Đơn chất
├── Đơn chất kim loại
└── Đơn chất phi kim
Oxit
├── Oxit bazơ
├── Oxit axit
├── Oxit lưỡng tính
├── Oxit trung tính
└── Oxit hỗn hợp
Axit
Bazơ
Muối
├── Muối trung hoà
└── Muối axit
Amoniac
```

Độ tan của bazơ được suy từ quy tắc, nên không tách thêm lớp “bazơ tan” và “bazơ không tan”.

Thứ tự xếp lớp:

1. Công thức nằm trong danh sách đặc biệt thì lấy lớp đã chỉ định. Hiện có NH3 là amoniac và H2O là oxit trung tính.
2. Công thức một nguyên tố: kim loại thành đơn chất kim loại, phần còn lại thành đơn chất phi kim.
3. Công thức đúng hai nguyên tố và có oxi: nếu không suy được một hoá trị duy nhất thì là oxit hỗn hợp; nếu nằm trong danh sách oxit trung tính thì là oxit trung tính (CO và H2O); nếu nguyên tố kia thuộc nhóm lưỡng tính thì là oxit lưỡng tính; nếu nguyên tố kia là phi kim thì là oxit axit; nếu là kim loại thì là oxit bazơ.
4. Công thức còn lại được tách cation và anion. Tổng điện tích phải bằng 0. Anion OH cho bazơ. Cation H cho axit. Anion hiđrocacbonat cho muối axit. Phần còn lại là muối trung hoà.

Bảng anion có 11 ion: HCO3, OH, NO3, AlO2 và Cl mang điện −1; SO4, SO3, CO3, ZnO2 và S mang điện −2; PO4 mang điện −3.

Độ tan lấy quy tắc khớp đầu tiên. Mỗi quy tắc luôn có chỗ cho một cation, một danh sách cation, một anion và một danh sách anion. Chỗ không dùng thì để trống. Kết quả là tan, ít tan hoặc không tan.

1. Muối và bazơ của Na, K, NH4 đều tan.
2. Mọi nitrat tan.
3. AgCl không tan.
4. Clorua còn lại tan.
5. BaSO4 không tan.
6. CaSO4 ít tan.
7. Sunfat còn lại tan.
8. NaOH, KOH và Ba(OH)2 tan.
9. Ca(OH)2 ít tan.
10. Hiđroxit còn lại không tan.
11. Hiđrocacbonat tan.
12. Cacbonat, sunfit, photphat và sunfua của kim loại khác không tan.
13. Aluminat và zicat tan.

### 3.5. Luật R2: phản ứng theo lớp

R2 lưu luật theo lớp chất, không lưu từng phương trình. Mỗi luật có cùng một lược đồ. Chỗ không dùng thì là danh sách rỗng hoặc để trống, để mọi luật cùng một hình dạng.

Một luật gồm: mã, kiểu máy sinh phản ứng, tên luật bằng tiếng Việt, các lớp được xét, các nhóm nguyên tố được xét, điều kiện của cả phản ứng, điều kiện riêng của từng chất, độ tan bắt buộc, danh sách chất bị loại, kim loại bị loại, axit bị loại, anion bị loại, cation bị loại, độ tan bị loại, thuốc thử cố định và khí sản phẩm cố định nếu có.

Nguyên tắc ngoại lệ là ghi chất nào không phản ứng. Danh sách dương, tức danh sách những chất nào được phản ứng, không được dùng để thay cho luật lớp. Tính kiềm, kiềm thổ hay đứng trước hiđro là thuộc tính của nguyên tố, nên được nêu trong luật như một điều kiện của lớp.

Lúc giải, máy áp từng luật lên các chất đang có, lập phương trình, rồi cân bằng bằng bảo toàn nguyên tố. Phương trình không cân được thì bỏ. Phương trình trùng thì chỉ giữ một bản. Với bộ tri thức hiện tại, bước này sinh ra 438 phương trình.

| Luật | Số phương trình sinh ra | Nội dung |
| --- | ---: | --- |
| Hai muối tan trao đổi ion khi tạo kết tủa | 107 | Cả hai muối tan, sản phẩm có kết tủa |
| Muối tan tác dụng với bazơ tan khi tạo kết tủa | 65 | Một sản phẩm không tan hoặc ít tan |
| Kim loại hoạt động hơn đẩy kim loại kém hoạt động khỏi muối tan | 44 | Loại Na, K, Ca, Ba |
| Axit tác dụng với bazơ | 41 | Tạo muối và nước |
| Oxit bazơ hoặc oxit lưỡng tính tác dụng với axit | 41 | Tạo muối và nước |
| Muối của axit yếu không bền tác dụng với axit mạnh hơn | 36 | Giải phóng khí; loại sunfat và photphat |
| Kim loại đứng trước hiđro tác dụng với axit | 16 | Giải phóng H2; H2SO4 chỉ khi loãng; loại HNO3, H3PO4, H2CO3, H2SO3 |
| Đơn chất cháy trong oxi | 14 | Cần đun; loại O2, N2, Cl2 và Ag |
| Oxit axit tác dụng với bazơ tan hoặc ít tan | 13 | Loại SiO2 và bazơ không tan |
| Muối aluminat hoặc zicat tác dụng với axit | 12 | Tạo hiđroxit lưỡng tính |
| Điện phân nóng chảy muối halogenua hoặc sunfua của kim loại kiềm và kiềm thổ | 7 | Ra kim loại và phi kim |
| Oxit, hiđroxit hoặc kim loại lưỡng tính tác dụng với dung dịch kiềm | 6 | Tạo aluminat hoặc zicat |
| Bazơ không tan bị nhiệt phân | 6 | Cần đun, ra oxit và nước |
| Oxit bazơ của kim loại kiềm và kiềm thổ tác dụng với nước | 5 | Ra bazơ |
| Kim loại kiềm và kiềm thổ tác dụng với nước | 5 | Mg cần đun |
| Oxit axit tác dụng với nước | 4 | Loại SiO2 |
| Cacbonat bị nhiệt phân | 4 | Loại muối của Na, K và NH4 |
| Amoniac tác dụng với axit | 4 | Ra muối amoni |
| Hiđro khử oxit kim loại khi đun | 4 | Loại Na, K, Ba, Ca, Mg, Al, Zn |
| Oxit hỗn hợp tác dụng với axit | 2 | Ra hai muối; loại HNO3 |
| Kim loại đứng sau hiđro tác dụng với H2SO4 đặc nóng | 1 | Ra muối, SO2 và nước; loại Ag |
| Oxit axit hoá trị thấp bị oxi hoá thành oxit axit hoá trị cao hơn | 1 | Cần đun và xúc tác; trong bộ hiện tại là SO2 thành SO3 |

Vài quy tắc sinh phản ứng cần được nêu rõ vì chúng quyết định phương trình nào xuất hiện:

- Muối của kim loại được chọn ở hoá trị thấp nhất còn có muối trong cơ sở. Sắt với HCl cho muối sắt(II). Đồng dùng hoá trị +2.
- Axit tương ứng của một oxit axit được suy bằng cách tách nước, không lưu cặp oxit–axit sẵn. SiO2 bị loại. Từ đó CO2 đi với H2CO3, SO2 đi với H2SO3, SO3 đi với H2SO4, P2O5 đi với H3PO4.
- Sản phẩm cháy cũng được suy: phi kim cho oxit axit hoá trị thấp nhất, nên lưu huỳnh cho SO2 và cacbon cho CO2; hiđro cho nước; sắt cho Fe3O4; kim loại còn lại cho oxit hoá trị cao nhất, nên đồng cho CuO.
- Kim loại lưỡng tính với kiềm được thử với muối và H2 trước. Nếu chưa cân thì thêm nước. Kẽm cho Na2ZnO2 và H2. Nhôm cần nước để cho NaAlO2 và H2.
- Oxi hoá oxit axit chỉ xảy ra khi cùng nguyên tố còn một oxit axit hoá trị cao hơn. Phương trình 2SO2 + O2 → 2SO3 được sinh ra, với điều kiện đun và xúc tác, chứ không được ghi sẵn trong luật.
- Điện phân nóng chảy áp dụng cho muối có cation kiềm hoặc kiềm thổ và anion một nguyên tố, không chứa oxi. Có NaCl, KCl, CaCl2, BaCl2, MgCl2, Na2S và K2S. AlCl3 không thuộc lớp này.
- Đường từ Al2O3 đến Al đi qua muối rồi dùng magiê đẩy nhôm, vì magiê đứng trước nhôm trong dãy hoạt động.

Độ sâu chuỗi tối đa là 5. Đây là một tham số của R2, không phải một đường đi lưu sẵn.

### 3.6. Luật R3: công thức lượng chất

R3 có một hằng số và năm quan hệ. Mỗi quan hệ được lưu thành một đẳng thức có vế trái, vế phải và đơn vị. Máy tính dùng đúng các quan hệ đó, và dùng được theo cả hai chiều khi dữ kiện cho phép.

| Quan hệ | Nội dung |
| --- | --- |
| Vm | 22,4 lít/mol, thể tích mol khí ở điều kiện tiêu chuẩn |
| Khối lượng mol | M bằng tổng của số nguyên tử nhân khối lượng nguyên tử |
| Khối lượng và số mol | n = m / M, và m = n × M khi khối lượng là đại lượng cần tìm |
| Thể tích khí | n = V / Vm, chỉ với chất khí; chiều ngược lại tính V khi V là mục tiêu |
| Nồng độ mol | n = CM × Vdd; từ đó tính được CM hoặc Vdd khi đã có số mol và đại lượng còn lại |
| Tỉ lệ hệ số | n1 / hệ số 1 = n2 / hệ số 2 |

Tỉ lệ hệ số chạy hai chiều. Số mol chất tham gia xác định mức phản ứng. Số mol sản phẩm cũng xác định được mức phản ứng. Nếu biết nhiều chất tham gia, mức phản ứng lấy theo chất hết trước và chất còn lại được ghi là dư. Nếu sản phẩm đòi một mức lớn hơn mức chất tham gia cho phép, dữ kiện bị coi là không khớp.

### 3.7. Tính nhất quán của tri thức

Mọi bản ghi trong cùng một thành phần dùng cùng các trường. Trường không có giá trị thì là danh sách rỗng hoặc để trống, không bị bỏ khoá.

Khi thêm hoặc sửa, hệ thống kiểm tra toàn bộ rồi mới giữ thay đổi:

- Ký hiệu, số hiệu nguyên tử, tên, mã lớp, mã luật và ký hiệu hằng số không được trùng.
- Lớp con phải tồn tại, mỗi lớp chỉ một cha, không có vòng, và nhãn lớp trên hợp chất phải đúng tên lớp.
- Lớp đặc biệt, oxit trung tính, anion muối axit, quy tắc độ tan và luật phản ứng phải trỏ tới nguyên tố, hợp chất, lớp, anion hoặc điều kiện đang có.
- Xoá một điều kiện, một lớp hoặc một hợp chất trong khi luật khác còn trỏ tới thì bị từ chối.

## 4. Bộ suy diễn

Bộ suy diễn có một cửa vào. Đề mang số dạng 1, 2 hoặc 3. Kết quả luôn có cờ có lời giải hay không, có vết các bước, và có đoạn văn trình bày. Có lời giải thì kèm phương trình, chuỗi, hoặc trị số và đơn vị. Không có lời giải thì kèm lý do.

Vết là danh sách các bước máy đã thực sự dùng. Mỗi bước ghi chiều suy diễn, mã luật và nội dung. Chiều tiến đi từ dữ kiện ra kết quả. Chiều lùi đi từ mục tiêu về dữ kiện. Đoạn văn ở mục 5 được dựng từ chính vết này, không được viết thêm một lập luận mà máy không chạy.

### 4.1. Dạng 1: suy diễn tiến trên bảo toàn nguyên tố

Quy trình:

1. Tách sơ đồ thành chất ở vế trái và vế phải.
2. Kiểm tra từng chất có trong cơ sở và ghi lớp mà R1 đã xếp.
3. Lập một phương trình cho mỗi nguyên tố: tổng số nguyên tử vế trái trừ tổng số nguyên tử vế phải bằng 0.
4. Giải hệ trên số hữu tỉ. Biến tự do được thử các giá trị nguyên dương nhỏ. Nghiệm được quy đồng mẫu và rút gọn ước chung.
5. Nếu không có nghiệm toàn số dương, bài không có lời giải.
6. Với mỗi nguyên tố, ghi một bước bảo toàn, rồi ghi phương trình đã cân bằng.

Sơ đồ Al2O3 + HCl → AlCl3 + H2O và sơ đồ thiếu nguyên tố H2O → H2 + NaCl có đầu ra đầy đủ ở mục 6.1 và mục 6.2. Đảo hai vế của một sơ đồ hợp lệ cho phương trình đảo với cùng bộ hệ số.

### 4.2. Dạng 2: suy diễn lùi tìm chuỗi ngắn nhất

Quy trình:

1. Kiểm tra chế độ. Chế độ chỉ chất cho trước bắt buộc có danh sách chất được phép. Danh sách rỗng vẫn hợp lệ: khi đó chỉ còn các phản ứng phân huỷ không cần thuốc thử thêm.
2. Kiểm tra chất đầu, chất đích và các chất cho trước đều có trong cơ sở.
3. Nếu chất đầu trùng chất đích, chuỗi rỗng và bài có lời giải.
4. Sinh toàn bộ phản ứng cụ thể từ 22 luật.
5. Dựng bảng “sản phẩm này có thể đến từ chất phản ứng nào”.
6. Tìm theo chiều rộng, đi lùi từ chất đích về chất đầu. Hàng đợi bảo đảm chuỗi ngắn nhất được gặp trước.
7. Dừng khi độ sâu vượt 5 hoặc không còn nút để đi.
8. Khi tìm được, ghi từng phản ứng vào vết theo chiều lùi, kèm tên luật và phương trình.

Một bước chỉ được nhận khi đủ ba điều kiện.

**Chuyển tiếp nguyên tố.** Nguyên tố được theo dõi là các nguyên tố khác hiđro và oxi. Nếu chất chỉ gồm hiđro và oxi thì chính hai nguyên tố đó được theo dõi. Chất trung gian phải mang hết nguyên tố đặc trưng chung của chất đầu và chất đích. Nhờ vậy nước, vốn thường là sản phẩm phụ, không được dùng làm cầu để đi từ một chất sang một nguyên tố không liên quan. Nước không được coi là đường điều chế natri.

Nếu chất đầu không chứa nguyên tố đặc trưng của chất đích, bước đó chỉ được nhận khi sản phẩm là chính đơn chất cần tìm. Sắt đẩy đồng khỏi muối đồng vẫn hợp lệ vì sản phẩm là đồng.

**Thuốc thử độc lập.** Thuốc thử không được là chất đích và không được là sản phẩm của một bước đã nằm trên đường đi. Đường đi không được dùng chính chất cần điều chế làm nguyên liệu của bước trước.

**Đúng chế độ.** Ở chế độ cho trước, mọi chất phản ứng ngoài chất đang truy phải thuộc danh sách cho phép hoặc chính là chất đầu.

Các chuỗi tiêu biểu, với đầu ra đầy đủ ở mục 6.4 đến mục 6.10, là:

- Từ lưu huỳnh đến axit sunfuric, ba bước qua SO2 và SO3.
- Từ natri clorua đến natri, và cũng từ natri clorua đến clo, cùng một phản ứng điện phân nóng chảy.
- Từ đồng đến đồng(II) hiđroxit khi chỉ được dùng O2, HCl và NaOH.
- Từ Al2O3 đến Al, qua muối rồi magiê đẩy nhôm.
- Từ bạc đến natri, và từ nước đến natri: không có đường trong phạm vi luật.

### 4.3. Dạng 3: suy diễn tiến trên công thức lượng chất

Nếu đề đã cho phương trình, máy cân bằng lại phương trình đó. Nếu không bảo toàn nguyên tố thì dừng. Nếu đề chỉ nêu các chất tham gia, máy tìm đúng một phản ứng R2 có tập chất phản ứng trùng đề và có chất cần tìm nằm trong phản ứng. Không có phản ứng nào thì dừng. Có nhiều phản ứng cùng khớp thì đề phải nêu phương trình.

Sau khi đã có phương trình, máy lặp các quy tắc sau cho đến khi có đại lượng cần tìm hoặc không sinh thêm sự kiện:

1. Tính khối lượng mol của mọi chất từ thành phần và khối lượng nguyên tử.
2. Nạp dữ kiện đề. Số liệu đề cho không bị ghi đè.
3. Có khối lượng và khối lượng mol thì tính số mol. Có số mol và khối lượng là mục tiêu thì tính khối lượng.
4. Với chất khí, có thể tích thì tính số mol; có số mol và thể tích là mục tiêu thì tính thể tích.
5. Có nồng độ và thể tích dung dịch thì tính số mol; có số mol và một trong hai thì tính đại lượng còn lại.
6. Khi đã có ít nhất một số mol của chất phản ứng hoặc sản phẩm, áp dụng tỉ lệ hệ số một lần. Mức phản ứng lấy theo chất hết trước, hoặc theo sản phẩm nếu đề cho sản phẩm. Nhiều sản phẩm phải cho cùng một mức. Mức theo sản phẩm không được lớn hơn mức theo chất tham gia.
7. Số mol vừa suy ra được dùng ở vòng sau để tính khối lượng hoặc thể tích nếu đó là mục tiêu.

Bốn tình huống lượng chất có đầu ra đầy đủ ở mục 6.11 đến mục 6.14:

- Từ 6,5 gam Zn và HCl, tìm thể tích H2.
- Đi ngược từ 2,24 lít H2 đã thu, tìm khối lượng ZnCl2.
- 0,2 mol Zn với 0,1 mol HCl, HCl hết trước.
- 0,1 mol HCl nhưng thu 0,1 mol H2: dữ kiện không khớp, bài bị từ chối.

Nếu mục tiêu vẫn thiếu, máy chỉ ra dữ kiện còn thiếu: thể tích khí đòi chất phải là khí; khối lượng đòi số mol; nồng độ đòi thể tích dung dịch; thể tích dung dịch đòi nồng độ.

## 5. Trình bày lời giải như lời diễn giải

Bản kết quả có cấu trúc dùng để kiểm tra: phương trình, danh sách bước, trị số và đơn vị. Người đọc cần một bài giải viết liền mạch. Lớp trình bày đứng sau bộ suy diễn. Nó không tính lại và không thêm lập luận. Nó chỉ chọn mẫu câu, điền giá trị đã tìm được, rồi nối các câu.

### 5.1. Mẫu câu và chỗ trống

Các mẫu được lưu cùng tri thức, tách khỏi luật hoá học. Mỗi mẫu là một khung tiếng Việt với các chỗ trống, ví dụ `{phuong_trinh}`, `{chat}`, `{ket_qua}`, `{don_vi_chu}`. Mẫu không chứa đáp án của một bài cụ thể. Cùng một mẫu “thể tích khí {chat} bằng {n} mol nhân với {vm} lít/mol, được {V} lít” được dùng cho mọi bài tính thể tích khí.

Ba mẫu nối câu quyết định giọng của bài giải:

- Câu đầu: “Đầu tiên, {cau}”.
- Câu giữa: “Tiếp theo, {cau}”.
- Câu chốt: “Vậy, {cau}”.

Nếu bài chỉ có một câu, câu đó dùng mẫu chốt. Số và đơn vị trong đoạn văn theo cách viết sách giáo khoa: 6,5 gam, 2,24 lít, 0,1 mol, 22,4 lít/mol. Công thức hoá học giữ nguyên ký hiệu.

### 5.2. Cách chọn và ghép mẫu

Mỗi bước trong vết mang một mã mẫu, ứng với tình huống vừa xảy ra: kiểm tra lớp chất, bảo toàn một nguyên tố, mở đầu một chuỗi, một phản ứng trong chuỗi, chọn phản ứng để tính, khối lượng mol, dữ kiện đề, đổi khối lượng ra số mol, đổi thể tích khí, đổi nồng độ, mức phản ứng, chất dư. Bộ trình bày đi theo đúng thứ tự vết, lấy mẫu có mã đó và điền tham số của bước.

Cuối bài, mã trường hợp của cả đề chọn một mẫu chốt. Các trường hợp đã có mẫu riêng gồm:

- Dạng 1 có phương trình, hoặc sơ đồ không bảo toàn.
- Dạng 2 có chuỗi, không có đường, hoặc chất đầu đã là chất đích.
- Dạng 3 có trị số; phương trình đề không bảo toàn; không có phản ứng phù hợp; có nhiều phản ứng nên đề phải nêu phương trình; các sản phẩm cho hai mức phản ứng khác nhau; sản phẩm đòi mức lớn hơn chất tham gia; chất cần tính thể tích không phải khí; thiếu số mol, thiếu khối lượng mol, thiếu thể tích dung dịch hoặc thiếu nồng độ.
- Đề không hợp lệ hoặc không thuộc ba dạng.

Câu chốt được gắn vào cuối danh sách câu, rồi ba mẫu nối câu được áp lên danh sách đó. Vì câu được sinh từ bước máy đã chạy, đoạn văn và vết kiểm tra kể cùng một lập luận.

Khi lời giải thích nội bộ của một phản ứng còn mã máy, như mã độ tan hay mã quy tắc, câu văn dùng tên luật tiếng Việt. Tên luật vốn là một câu trong chương trình, ví dụ “dung dịch muối tác dụng với dung dịch bazơ khi tạo kết tủa”.

### 5.3. Hình dạng bản trả về

Mỗi lần giải trả về một bản ghi đủ các thành phần sau. Không có trường nào bị lược khi in kết quả.

| Trường | Khi nào có | Ý nghĩa |
| --- | --- | --- |
| `co_loi_giai` | Luôn có | Có tìm được kết quả hay không |
| `phuong_trinh`, `he_so` | Dạng 1 có lời giải | Phương trình đã cân bằng và dãy hệ số |
| `che_do`, `chuoi`, `so_buoc` | Dạng 2 | Chế độ thuốc thử, các phương trình và số bước |
| `ket_qua`, `don_vi`, `dai_luong` | Dạng 3 có lời giải | Trị số máy đọc được, đơn vị ký hiệu và đại lượng |
| `thong_bao` | Không có lời giải | Lý do dừng |
| `phuong_trinh_ung_vien` | Dạng 3 có nhiều phản ứng cùng khớp | Các phương trình để người ra đề chọn |
| `vet` | Luôn có | Từng bước suy diễn: số bước, chiều `tien` hoặc `lui`, mã luật, nội dung |
| `trinh_bay` | Luôn có | Bài giải tiếng Việt, ghép từ mẫu câu và các giá trị trong vết |

Trị số trong `ket_qua` giữ dấu chấm để chương trình khác đọc, ví dụ `2.24` và đơn vị `L`. Cùng con số đó trong `trinh_bay` được viết `2,24 lít`. Đoạn văn không phải bản tóm tắt riêng: nó kể đủ các bước có trong `vet`, từ xếp lớp đến câu chốt.

Bản đầy đủ của bài 6,5 gam Zn nằm ở mục 6.11. Bản đầy đủ của bài cân bằng Al2O3 nằm ở mục 6.1. Bản đầy đủ của bài bạc không điều chế được natri nằm ở mục 6.9.

## 6. Ví dụ và kết quả đầu ra đầy đủ

Các bản dưới đây là đúng đối tượng hệ thống trả về sau khi suy diễn và ghép mẫu câu. Đầu vào ghi đề. Đầu ra gồm cờ lời giải, kết quả có cấu trúc, vết từng bước và trường `trinh_bay`.

### 6.1. Cân bằng Al2O3 với HCl

Đầu vào:

```json
{
  "loai": 1,
  "phan_ung": "Al2O3 + HCl -> AlCl3 + H2O"
}
```

Đầu ra đầy đủ:

```json
{
  "co_loi_giai": true,
  "phuong_trinh": "Al2O3 + 6HCl → 2AlCl3 + 3H2O",
  "he_so": [
    1,
    6,
    2,
    3
  ],
  "vet": [
    {
      "buoc": 1,
      "chieu": "tien",
      "luat": "R1",
      "noi_dung": "Kiểm tra Al2O3: R1 xếp vào lớp Oxit lưỡng tính. Thành phần ['Al2', 'O3']."
    },
    {
      "buoc": 2,
      "chieu": "tien",
      "luat": "R1",
      "noi_dung": "Kiểm tra HCl: R1 xếp vào lớp Axit. Thành phần ['H', 'Cl']."
    },
    {
      "buoc": 3,
      "chieu": "tien",
      "luat": "R1",
      "noi_dung": "Kiểm tra AlCl3: R1 xếp vào lớp Muối trung hoà. Thành phần ['Al', 'Cl3']."
    },
    {
      "buoc": 4,
      "chieu": "tien",
      "luat": "R1",
      "noi_dung": "Kiểm tra H2O: R1 xếp vào lớp Oxit trung tính. Thành phần ['H2', 'O']."
    },
    {
      "buoc": 5,
      "chieu": "tien",
      "luat": "BAO_TOAN",
      "noi_dung": "Bảo toàn Al: vế trái 2 nguyên tử, vế phải 2 nguyên tử."
    },
    {
      "buoc": 6,
      "chieu": "tien",
      "luat": "BAO_TOAN",
      "noi_dung": "Bảo toàn Cl: vế trái 6 nguyên tử, vế phải 6 nguyên tử."
    },
    {
      "buoc": 7,
      "chieu": "tien",
      "luat": "BAO_TOAN",
      "noi_dung": "Bảo toàn H: vế trái 6 nguyên tử, vế phải 6 nguyên tử."
    },
    {
      "buoc": 8,
      "chieu": "tien",
      "luat": "BAO_TOAN",
      "noi_dung": "Bảo toàn O: vế trái 3 nguyên tử, vế phải 3 nguyên tử."
    },
    {
      "buoc": 9,
      "chieu": "tien",
      "luat": "BAO_TOAN",
      "noi_dung": "Hệ số nguyên dương nhỏ nhất cho Al2O3 + 6HCl → 2AlCl3 + 3H2O."
    }
  ],
  "trinh_bay": "Đầu tiên, Al2O3 thuộc lớp oxit lưỡng tính.\nTiếp theo, HCl thuộc lớp axit.\nTiếp theo, AlCl3 thuộc lớp muối trung hoà.\nTiếp theo, H2O thuộc lớp oxit trung tính.\nTiếp theo, bảo toàn nguyên tố nhôm (Al): vế trái có 2 nguyên tử và vế phải có 2 nguyên tử.\nTiếp theo, bảo toàn nguyên tố clo (Cl): vế trái có 6 nguyên tử và vế phải có 6 nguyên tử.\nTiếp theo, bảo toàn nguyên tố hiđro (H): vế trái có 6 nguyên tử và vế phải có 6 nguyên tử.\nTiếp theo, bảo toàn nguyên tố oxi (O): vế trái có 3 nguyên tử và vế phải có 3 nguyên tử.\nVậy, phương trình cân bằng là Al2O3 + 6HCl → 2AlCl3 + 3H2O."
}
```

### 6.2. Sơ đồ không bảo toàn nguyên tố

Đầu vào:

```json
{
  "loai": 1,
  "phan_ung": "H2O -> H2 + NaCl"
}
```

Đầu ra đầy đủ:

```json
{
  "co_loi_giai": false,
  "thong_bao": "Không có bộ hệ số nguyên dương nào bảo toàn mọi nguyên tố.",
  "vet": [
    {
      "buoc": 1,
      "chieu": "tien",
      "luat": "R1",
      "noi_dung": "Kiểm tra H2O: R1 xếp vào lớp Oxit trung tính. Thành phần ['H2', 'O']."
    },
    {
      "buoc": 2,
      "chieu": "tien",
      "luat": "R1",
      "noi_dung": "Kiểm tra H2: R1 xếp vào lớp Đơn chất phi kim. Thành phần ['H2']."
    },
    {
      "buoc": 3,
      "chieu": "tien",
      "luat": "R1",
      "noi_dung": "Kiểm tra NaCl: R1 xếp vào lớp Muối trung hoà. Thành phần ['Na', 'Cl']."
    }
  ],
  "trinh_bay": "Đầu tiên, H2O thuộc lớp oxit trung tính.\nTiếp theo, H2 thuộc lớp đơn chất phi kim.\nTiếp theo, NaCl thuộc lớp muối trung hoà.\nVậy, sơ đồ H2O → H2 + NaCl không có bộ hệ số nguyên dương nào bảo toàn mọi nguyên tố."
}
```

### 6.3. Cân bằng oxit hỗn hợp Fe3O4

Đầu vào:

```json
{
  "loai": 1,
  "phan_ung": "Fe3O4 + HCl -> FeCl2 + FeCl3 + H2O"
}
```

Đầu ra đầy đủ:

```json
{
  "co_loi_giai": true,
  "phuong_trinh": "Fe3O4 + 8HCl → FeCl2 + 2FeCl3 + 4H2O",
  "he_so": [
    1,
    8,
    1,
    2,
    4
  ],
  "vet": [
    {
      "buoc": 1,
      "chieu": "tien",
      "luat": "R1",
      "noi_dung": "Kiểm tra Fe3O4: R1 xếp vào lớp Oxit hỗn hợp. Thành phần ['Fe3', 'O4']."
    },
    {
      "buoc": 2,
      "chieu": "tien",
      "luat": "R1",
      "noi_dung": "Kiểm tra HCl: R1 xếp vào lớp Axit. Thành phần ['H', 'Cl']."
    },
    {
      "buoc": 3,
      "chieu": "tien",
      "luat": "R1",
      "noi_dung": "Kiểm tra FeCl2: R1 xếp vào lớp Muối trung hoà. Thành phần ['Fe', 'Cl2']."
    },
    {
      "buoc": 4,
      "chieu": "tien",
      "luat": "R1",
      "noi_dung": "Kiểm tra FeCl3: R1 xếp vào lớp Muối trung hoà. Thành phần ['Fe', 'Cl3']."
    },
    {
      "buoc": 5,
      "chieu": "tien",
      "luat": "R1",
      "noi_dung": "Kiểm tra H2O: R1 xếp vào lớp Oxit trung tính. Thành phần ['H2', 'O']."
    },
    {
      "buoc": 6,
      "chieu": "tien",
      "luat": "BAO_TOAN",
      "noi_dung": "Bảo toàn Cl: vế trái 8 nguyên tử, vế phải 8 nguyên tử."
    },
    {
      "buoc": 7,
      "chieu": "tien",
      "luat": "BAO_TOAN",
      "noi_dung": "Bảo toàn Fe: vế trái 3 nguyên tử, vế phải 3 nguyên tử."
    },
    {
      "buoc": 8,
      "chieu": "tien",
      "luat": "BAO_TOAN",
      "noi_dung": "Bảo toàn H: vế trái 8 nguyên tử, vế phải 8 nguyên tử."
    },
    {
      "buoc": 9,
      "chieu": "tien",
      "luat": "BAO_TOAN",
      "noi_dung": "Bảo toàn O: vế trái 4 nguyên tử, vế phải 4 nguyên tử."
    },
    {
      "buoc": 10,
      "chieu": "tien",
      "luat": "BAO_TOAN",
      "noi_dung": "Hệ số nguyên dương nhỏ nhất cho Fe3O4 + 8HCl → FeCl2 + 2FeCl3 + 4H2O."
    }
  ],
  "trinh_bay": "Đầu tiên, Fe3O4 thuộc lớp oxit hỗn hợp.\nTiếp theo, HCl thuộc lớp axit.\nTiếp theo, FeCl2 thuộc lớp muối trung hoà.\nTiếp theo, FeCl3 thuộc lớp muối trung hoà.\nTiếp theo, H2O thuộc lớp oxit trung tính.\nTiếp theo, bảo toàn nguyên tố clo (Cl): vế trái có 8 nguyên tử và vế phải có 8 nguyên tử.\nTiếp theo, bảo toàn nguyên tố sắt (Fe): vế trái có 3 nguyên tử và vế phải có 3 nguyên tử.\nTiếp theo, bảo toàn nguyên tố hiđro (H): vế trái có 8 nguyên tử và vế phải có 8 nguyên tử.\nTiếp theo, bảo toàn nguyên tố oxi (O): vế trái có 4 nguyên tử và vế phải có 4 nguyên tử.\nVậy, phương trình cân bằng là Fe3O4 + 8HCl → FeCl2 + 2FeCl3 + 4H2O."
}
```

### 6.4. Chuỗi từ lưu huỳnh đến axit sunfuric

Đầu vào:

```json
{
  "loai": 2,
  "chat_dau": "S",
  "chat_dich": "H2SO4"
}
```

Đầu ra đầy đủ:

```json
{
  "co_loi_giai": true,
  "che_do": "tat_ca",
  "chuoi": [
    "S + O2 →[t°] SO2",
    "2SO2 + O2 →[t°, xúc tác] 2SO3",
    "SO3 + H2O → H2SO4"
  ],
  "so_buoc": 3,
  "vet": [
    {
      "buoc": 1,
      "chieu": "tien",
      "luat": "R1",
      "noi_dung": "Kiểm tra S: R1 xếp vào lớp Đơn chất phi kim. Thành phần ['S']."
    },
    {
      "buoc": 2,
      "chieu": "tien",
      "luat": "R1",
      "noi_dung": "Kiểm tra H2SO4: R1 xếp vào lớp Axit. Thành phần ['H2', 'S', 'O4']."
    },
    {
      "buoc": 3,
      "chieu": "lui",
      "luat": "R2",
      "noi_dung": "Đặt mục tiêu H2SO4. Suy diễn lùi từ chất đầu S. Mọi chất trong phạm vi THCS đều được dùng làm thuốc thử. Mỗi bước phải chuyển tiếp nguyên tố đặc trưng; sản phẩm phụ như H2O không được làm cầu nối. Độ sâu tối đa 5 phản ứng."
    },
    {
      "buoc": 4,
      "chieu": "lui",
      "luat": "R2_DOT_CHAY",
      "noi_dung": "Đơn chất cháy trong oxi. Sản phẩm là oxit của S. Phương trình: S + O2 →[t°] SO2."
    },
    {
      "buoc": 5,
      "chieu": "lui",
      "luat": "R2_OXIT_AXIT_OXI_HOA",
      "noi_dung": "Oxit axit chưa ở hoá trị cao nhất bị oxi hoá thành oxit axit hoá trị cao hơn. SO2 lên hoá trị 6, ra SO3. Phương trình: 2SO2 + O2 →[t°, xúc tác] 2SO3."
    },
    {
      "buoc": 6,
      "chieu": "lui",
      "luat": "R2_OXIT_AXIT_NUOC",
      "noi_dung": "Oxit axit tác dụng với nước. SO3 ứng với H2SO4. Phương trình: SO3 + H2O → H2SO4."
    }
  ],
  "trinh_bay": "Đầu tiên, S thuộc lớp đơn chất phi kim.\nTiếp theo, H2SO4 thuộc lớp axit.\nTiếp theo, đặt mục tiêu điều chế H2SO4 từ S, được dùng mọi thuốc thử trong chương trình, và chỉ nhận chuỗi ngắn nhất không quá 5 bước.\nTiếp theo, đơn chất cháy trong oxi. Sản phẩm là oxit của S, nên viết được phương trình S + O2 →[t°] SO2.\nTiếp theo, oxit axit chưa ở hoá trị cao nhất bị oxi hoá thành oxit axit hoá trị cao hơn. SO2 lên hoá trị 6, ra SO3, nên viết được phương trình 2SO2 + O2 →[t°, xúc tác] 2SO3.\nTiếp theo, oxit axit tác dụng với nước. SO3 ứng với H2SO4, nên viết được phương trình SO3 + H2O → H2SO4.\nVậy, điều chế được H2SO4 từ S bằng 3 bước: S + O2 →[t°] SO2; 2SO2 + O2 →[t°, xúc tác] 2SO3; SO3 + H2O → H2SO4."
}
```

### 6.5. Điện phân natri clorua nóng chảy ra natri

Đầu vào:

```json
{
  "loai": 2,
  "chat_dau": "NaCl",
  "chat_dich": "Na"
}
```

Đầu ra đầy đủ:

```json
{
  "co_loi_giai": true,
  "che_do": "tat_ca",
  "chuoi": [
    "2NaCl →[điện phân nóng chảy] 2Na + Cl2"
  ],
  "so_buoc": 1,
  "vet": [
    {
      "buoc": 1,
      "chieu": "tien",
      "luat": "R1",
      "noi_dung": "Kiểm tra NaCl: R1 xếp vào lớp Muối trung hoà. Thành phần ['Na', 'Cl']."
    },
    {
      "buoc": 2,
      "chieu": "tien",
      "luat": "R1",
      "noi_dung": "Kiểm tra Na: R1 xếp vào lớp Đơn chất kim loại. Thành phần ['Na']."
    },
    {
      "buoc": 3,
      "chieu": "lui",
      "luat": "R2",
      "noi_dung": "Đặt mục tiêu Na. Suy diễn lùi từ chất đầu NaCl. Mọi chất trong phạm vi THCS đều được dùng làm thuốc thử. Mỗi bước phải chuyển tiếp nguyên tố đặc trưng; sản phẩm phụ như H2O không được làm cầu nối. Độ sâu tối đa 5 phản ứng."
    },
    {
      "buoc": 4,
      "chieu": "lui",
      "luat": "R2_DIEN_PHAN_NONG_CHAY",
      "noi_dung": "Điện phân nóng chảy muối halogenua hoặc sunfua của kim loại kiềm và kiềm thổ. Anion Cl không chứa oxi. Phương trình: 2NaCl →[điện phân nóng chảy] 2Na + Cl2."
    }
  ],
  "trinh_bay": "Đầu tiên, NaCl thuộc lớp muối trung hoà.\nTiếp theo, Na thuộc lớp đơn chất kim loại.\nTiếp theo, đặt mục tiêu điều chế Na từ NaCl, được dùng mọi thuốc thử trong chương trình, và chỉ nhận chuỗi ngắn nhất không quá 5 bước.\nTiếp theo, điện phân nóng chảy muối halogenua hoặc sunfua của kim loại kiềm và kiềm thổ. Anion Cl không chứa oxi, nên viết được phương trình 2NaCl →[điện phân nóng chảy] 2Na + Cl2.\nVậy, điều chế được Na từ NaCl bằng 1 bước: 2NaCl →[điện phân nóng chảy] 2Na + Cl2."
}
```

### 6.6. Cùng phản ứng điện phân, chất đích là clo

Đầu vào:

```json
{
  "loai": 2,
  "chat_dau": "NaCl",
  "chat_dich": "Cl2"
}
```

Đầu ra đầy đủ:

```json
{
  "co_loi_giai": true,
  "che_do": "tat_ca",
  "chuoi": [
    "2NaCl →[điện phân nóng chảy] 2Na + Cl2"
  ],
  "so_buoc": 1,
  "vet": [
    {
      "buoc": 1,
      "chieu": "tien",
      "luat": "R1",
      "noi_dung": "Kiểm tra NaCl: R1 xếp vào lớp Muối trung hoà. Thành phần ['Na', 'Cl']."
    },
    {
      "buoc": 2,
      "chieu": "tien",
      "luat": "R1",
      "noi_dung": "Kiểm tra Cl2: R1 xếp vào lớp Đơn chất phi kim. Thành phần ['Cl2']."
    },
    {
      "buoc": 3,
      "chieu": "lui",
      "luat": "R2",
      "noi_dung": "Đặt mục tiêu Cl2. Suy diễn lùi từ chất đầu NaCl. Mọi chất trong phạm vi THCS đều được dùng làm thuốc thử. Mỗi bước phải chuyển tiếp nguyên tố đặc trưng; sản phẩm phụ như H2O không được làm cầu nối. Độ sâu tối đa 5 phản ứng."
    },
    {
      "buoc": 4,
      "chieu": "lui",
      "luat": "R2_DIEN_PHAN_NONG_CHAY",
      "noi_dung": "Điện phân nóng chảy muối halogenua hoặc sunfua của kim loại kiềm và kiềm thổ. Anion Cl không chứa oxi. Phương trình: 2NaCl →[điện phân nóng chảy] 2Na + Cl2."
    }
  ],
  "trinh_bay": "Đầu tiên, NaCl thuộc lớp muối trung hoà.\nTiếp theo, Cl2 thuộc lớp đơn chất phi kim.\nTiếp theo, đặt mục tiêu điều chế Cl2 từ NaCl, được dùng mọi thuốc thử trong chương trình, và chỉ nhận chuỗi ngắn nhất không quá 5 bước.\nTiếp theo, điện phân nóng chảy muối halogenua hoặc sunfua của kim loại kiềm và kiềm thổ. Anion Cl không chứa oxi, nên viết được phương trình 2NaCl →[điện phân nóng chảy] 2Na + Cl2.\nVậy, điều chế được Cl2 từ NaCl bằng 1 bước: 2NaCl →[điện phân nóng chảy] 2Na + Cl2."
}
```

### 6.7. Điều chế Cu(OH)2 khi chỉ được dùng O2, HCl và NaOH

Đầu vào:

```json
{
  "loai": 2,
  "chat_dau": "Cu",
  "chat_dich": "Cu(OH)2",
  "che_do": "cho_truoc",
  "chat_cho_phep": [
    "O2",
    "HCl",
    "NaOH"
  ]
}
```

Đầu ra đầy đủ:

```json
{
  "co_loi_giai": true,
  "che_do": "cho_truoc",
  "chuoi": [
    "2Cu + O2 →[t°] 2CuO",
    "CuO + 2HCl → CuCl2 + H2O",
    "CuCl2 + 2NaOH → 2NaCl + Cu(OH)2"
  ],
  "so_buoc": 3,
  "vet": [
    {
      "buoc": 1,
      "chieu": "tien",
      "luat": "R1",
      "noi_dung": "Kiểm tra O2: R1 xếp vào lớp Đơn chất phi kim. Thành phần ['O2']."
    },
    {
      "buoc": 2,
      "chieu": "tien",
      "luat": "R1",
      "noi_dung": "Kiểm tra HCl: R1 xếp vào lớp Axit. Thành phần ['H', 'Cl']."
    },
    {
      "buoc": 3,
      "chieu": "tien",
      "luat": "R1",
      "noi_dung": "Kiểm tra NaOH: R1 xếp vào lớp Bazơ. Thành phần ['Na', 'O', 'H']."
    },
    {
      "buoc": 4,
      "chieu": "tien",
      "luat": "R1",
      "noi_dung": "Kiểm tra Cu: R1 xếp vào lớp Đơn chất kim loại. Thành phần ['Cu']."
    },
    {
      "buoc": 5,
      "chieu": "tien",
      "luat": "R1",
      "noi_dung": "Kiểm tra Cu(OH)2: R1 xếp vào lớp Bazơ. Thành phần ['Cu', 'O2', 'H2']."
    },
    {
      "buoc": 6,
      "chieu": "lui",
      "luat": "R2",
      "noi_dung": "Đặt mục tiêu Cu(OH)2. Suy diễn lùi từ chất đầu Cu. Chỉ được dùng các chất cho trước: O2, HCl, NaOH. Chất sinh ra ở bước trước được dùng tiếp. Mỗi bước phải chuyển tiếp nguyên tố đặc trưng; sản phẩm phụ như H2O không được làm cầu nối. Độ sâu tối đa 5 phản ứng."
    },
    {
      "buoc": 7,
      "chieu": "lui",
      "luat": "R2_DOT_CHAY",
      "noi_dung": "Đơn chất cháy trong oxi. Sản phẩm là oxit của Cu. Phương trình: 2Cu + O2 →[t°] 2CuO."
    },
    {
      "buoc": 8,
      "chieu": "lui",
      "luat": "R2_OXIT_BAZO_AXIT",
      "noi_dung": "Oxit bazơ hoặc oxit lưỡng tính tác dụng với axit. Hoá trị của Cu trong CuO là 2. Phương trình: CuO + 2HCl → CuCl2 + H2O."
    },
    {
      "buoc": 9,
      "chieu": "lui",
      "luat": "R2_MUOI_BAZO",
      "noi_dung": "Dung dịch muối tác dụng với dung dịch bazơ khi tạo kết tủa. Cu(OH)2 khong_tan theo SOL_OH. Phương trình: CuCl2 + 2NaOH → 2NaCl + Cu(OH)2."
    }
  ],
  "trinh_bay": "Đầu tiên, O2 thuộc lớp đơn chất phi kim.\nTiếp theo, HCl thuộc lớp axit.\nTiếp theo, NaOH thuộc lớp bazơ.\nTiếp theo, Cu thuộc lớp đơn chất kim loại.\nTiếp theo, Cu(OH)2 thuộc lớp bazơ.\nTiếp theo, đặt mục tiêu điều chế Cu(OH)2 từ Cu, chỉ được dùng O2, HCl và NaOH; chất sinh ra ở bước trước được dùng tiếp, và chuỗi không quá 5 bước.\nTiếp theo, đơn chất cháy trong oxi. Sản phẩm là oxit của Cu, nên viết được phương trình 2Cu + O2 →[t°] 2CuO.\nTiếp theo, oxit bazơ hoặc oxit lưỡng tính tác dụng với axit. Hoá trị của Cu trong CuO là 2, nên viết được phương trình CuO + 2HCl → CuCl2 + H2O.\nTiếp theo, dung dịch muối tác dụng với dung dịch bazơ khi tạo kết tủa, nên viết được phương trình CuCl2 + 2NaOH → 2NaCl + Cu(OH)2.\nVậy, điều chế được Cu(OH)2 từ Cu bằng 3 bước: 2Cu + O2 →[t°] 2CuO; CuO + 2HCl → CuCl2 + H2O; CuCl2 + 2NaOH → 2NaCl + Cu(OH)2."
}
```

### 6.8. Từ Al2O3 đến Al

Đầu vào:

```json
{
  "loai": 2,
  "chat_dau": "Al2O3",
  "chat_dich": "Al"
}
```

Đầu ra đầy đủ:

```json
{
  "co_loi_giai": true,
  "che_do": "tat_ca",
  "chuoi": [
    "Al2O3 + 6HCl → 2AlCl3 + 3H2O",
    "3Mg + 2AlCl3 → 3MgCl2 + 2Al"
  ],
  "so_buoc": 2,
  "vet": [
    {
      "buoc": 1,
      "chieu": "tien",
      "luat": "R1",
      "noi_dung": "Kiểm tra Al2O3: R1 xếp vào lớp Oxit lưỡng tính. Thành phần ['Al2', 'O3']."
    },
    {
      "buoc": 2,
      "chieu": "tien",
      "luat": "R1",
      "noi_dung": "Kiểm tra Al: R1 xếp vào lớp Đơn chất kim loại. Thành phần ['Al']."
    },
    {
      "buoc": 3,
      "chieu": "lui",
      "luat": "R2",
      "noi_dung": "Đặt mục tiêu Al. Suy diễn lùi từ chất đầu Al2O3. Mọi chất trong phạm vi THCS đều được dùng làm thuốc thử. Mỗi bước phải chuyển tiếp nguyên tố đặc trưng; sản phẩm phụ như H2O không được làm cầu nối. Độ sâu tối đa 5 phản ứng."
    },
    {
      "buoc": 4,
      "chieu": "lui",
      "luat": "R2_OXIT_BAZO_AXIT",
      "noi_dung": "Oxit bazơ hoặc oxit lưỡng tính tác dụng với axit. Hoá trị của Al trong Al2O3 là 3. Phương trình: Al2O3 + 6HCl → 2AlCl3 + 3H2O."
    },
    {
      "buoc": 5,
      "chieu": "lui",
      "luat": "R2_KIM_LOAI_MUOI",
      "noi_dung": "Kim loại hoạt động hơn đẩy kim loại kém hoạt động ra khỏi muối. Mg hoạt động hơn Al (5 < 6). Muối mới lấy hoá trị thấp 2. Phương trình: 3Mg + 2AlCl3 → 3MgCl2 + 2Al."
    }
  ],
  "trinh_bay": "Đầu tiên, Al2O3 thuộc lớp oxit lưỡng tính.\nTiếp theo, Al thuộc lớp đơn chất kim loại.\nTiếp theo, đặt mục tiêu điều chế Al từ Al2O3, được dùng mọi thuốc thử trong chương trình, và chỉ nhận chuỗi ngắn nhất không quá 5 bước.\nTiếp theo, oxit bazơ hoặc oxit lưỡng tính tác dụng với axit. Hoá trị của Al trong Al2O3 là 3, nên viết được phương trình Al2O3 + 6HCl → 2AlCl3 + 3H2O.\nTiếp theo, kim loại hoạt động hơn đẩy kim loại kém hoạt động ra khỏi muối. Mg hoạt động hơn Al (5 < 6). Muối mới lấy hoá trị thấp 2, nên viết được phương trình 3Mg + 2AlCl3 → 3MgCl2 + 2Al.\nVậy, điều chế được Al từ Al2O3 bằng 2 bước: Al2O3 + 6HCl → 2AlCl3 + 3H2O; 3Mg + 2AlCl3 → 3MgCl2 + 2Al."
}
```

### 6.9. Không có đường từ bạc đến natri

Đầu vào:

```json
{
  "loai": 2,
  "chat_dau": "Ag",
  "chat_dich": "Na"
}
```

Đầu ra đầy đủ:

```json
{
  "co_loi_giai": false,
  "che_do": "tat_ca",
  "thong_bao": "Không tìm thấy chuỗi từ Ag tới Na trong phạm vi luật, tối đa 5 bước. Các bước phải chuyển tiếp nguyên tố đặc trưng, không nối qua sản phẩm phụ.",
  "vet": [
    {
      "buoc": 1,
      "chieu": "tien",
      "luat": "R1",
      "noi_dung": "Kiểm tra Ag: R1 xếp vào lớp Đơn chất kim loại. Thành phần ['Ag']."
    },
    {
      "buoc": 2,
      "chieu": "tien",
      "luat": "R1",
      "noi_dung": "Kiểm tra Na: R1 xếp vào lớp Đơn chất kim loại. Thành phần ['Na']."
    },
    {
      "buoc": 3,
      "chieu": "lui",
      "luat": "R2",
      "noi_dung": "Đặt mục tiêu Na. Suy diễn lùi từ chất đầu Ag. Mọi chất trong phạm vi THCS đều được dùng làm thuốc thử. Mỗi bước phải chuyển tiếp nguyên tố đặc trưng; sản phẩm phụ như H2O không được làm cầu nối. Độ sâu tối đa 5 phản ứng."
    }
  ],
  "trinh_bay": "Đầu tiên, Ag thuộc lớp đơn chất kim loại.\nTiếp theo, Na thuộc lớp đơn chất kim loại.\nTiếp theo, đặt mục tiêu điều chế Na từ Ag, được dùng mọi thuốc thử trong chương trình, và chỉ nhận chuỗi ngắn nhất không quá 5 bước.\nVậy, không tìm được chuỗi từ Ag đến Na trong phạm vi thuốc thử của chương trình, với độ sâu tối đa 5 bước và không nối qua sản phẩm phụ."
}
```

### 6.10. Nước không phải đường điều chế natri

Đầu vào:

```json
{
  "loai": 2,
  "chat_dau": "H2O",
  "chat_dich": "Na"
}
```

Đầu ra đầy đủ:

```json
{
  "co_loi_giai": false,
  "che_do": "tat_ca",
  "thong_bao": "Không tìm thấy chuỗi từ H2O tới Na trong phạm vi luật, tối đa 5 bước. Các bước phải chuyển tiếp nguyên tố đặc trưng, không nối qua sản phẩm phụ.",
  "vet": [
    {
      "buoc": 1,
      "chieu": "tien",
      "luat": "R1",
      "noi_dung": "Kiểm tra H2O: R1 xếp vào lớp Oxit trung tính. Thành phần ['H2', 'O']."
    },
    {
      "buoc": 2,
      "chieu": "tien",
      "luat": "R1",
      "noi_dung": "Kiểm tra Na: R1 xếp vào lớp Đơn chất kim loại. Thành phần ['Na']."
    },
    {
      "buoc": 3,
      "chieu": "lui",
      "luat": "R2",
      "noi_dung": "Đặt mục tiêu Na. Suy diễn lùi từ chất đầu H2O. Mọi chất trong phạm vi THCS đều được dùng làm thuốc thử. Mỗi bước phải chuyển tiếp nguyên tố đặc trưng; sản phẩm phụ như H2O không được làm cầu nối. Độ sâu tối đa 5 phản ứng."
    }
  ],
  "trinh_bay": "Đầu tiên, H2O thuộc lớp oxit trung tính.\nTiếp theo, Na thuộc lớp đơn chất kim loại.\nTiếp theo, đặt mục tiêu điều chế Na từ H2O, được dùng mọi thuốc thử trong chương trình, và chỉ nhận chuỗi ngắn nhất không quá 5 bước.\nVậy, không tìm được chuỗi từ H2O đến Na trong phạm vi thuốc thử của chương trình, với độ sâu tối đa 5 bước và không nối qua sản phẩm phụ."
}
```

### 6.11. 6,5 gam Zn với HCl, tìm thể tích H2

Đầu vào:

```json
{
  "loai": 3,
  "chat_tham_gia": [
    "Zn",
    "HCl"
  ],
  "biet": [
    {
      "chat": "Zn",
      "dai_luong": "m",
      "gia_tri": 6.5
    }
  ],
  "tim": {
    "chat": "H2",
    "dai_luong": "V"
  }
}
```

Đầu ra đầy đủ:

```json
{
  "co_loi_giai": true,
  "ket_qua": "2.24",
  "don_vi": "L",
  "dai_luong": "V(H2)",
  "vet": [
    {
      "buoc": 1,
      "chieu": "tien",
      "luat": "R1",
      "noi_dung": "Kiểm tra Zn: R1 xếp vào lớp Đơn chất kim loại. Thành phần ['Zn']."
    },
    {
      "buoc": 2,
      "chieu": "tien",
      "luat": "R1",
      "noi_dung": "Kiểm tra HCl: R1 xếp vào lớp Axit. Thành phần ['H', 'Cl']."
    },
    {
      "buoc": 3,
      "chieu": "tien",
      "luat": "R2_KIM_LOAI_AXIT",
      "noi_dung": "Chọn phản ứng từ luật: Kim loại đứng trước hiđro tác dụng với axit tạo muối và hiđro. Kẽm đứng trước hiđro (mức hoạt động 7 nhỏ hơn 12), hoá trị 2. Zn + 2HCl → ZnCl2 + H2."
    },
    {
      "buoc": 4,
      "chieu": "tien",
      "luat": "C_VM",
      "noi_dung": "Thể tích mol khí ở đktc Vm = 22.4 L/mol."
    },
    {
      "buoc": 5,
      "chieu": "tien",
      "luat": "F_MOL_MASS",
      "noi_dung": "M(Zn) = 1×65 = 65 g/mol."
    },
    {
      "buoc": 6,
      "chieu": "tien",
      "luat": "F_MOL_MASS",
      "noi_dung": "M(HCl) = 1×1 + 1×35.5 = 36.5 g/mol."
    },
    {
      "buoc": 7,
      "chieu": "tien",
      "luat": "F_MOL_MASS",
      "noi_dung": "M(ZnCl2) = 1×65 + 2×35.5 = 136 g/mol."
    },
    {
      "buoc": 8,
      "chieu": "tien",
      "luat": "F_MOL_MASS",
      "noi_dung": "M(H2) = 2×1 = 2 g/mol."
    },
    {
      "buoc": 9,
      "chieu": "tien",
      "luat": "DE_BAI",
      "noi_dung": "Giả thiết: m(Zn) = 6.5 g."
    },
    {
      "buoc": 10,
      "chieu": "tien",
      "luat": "F_N_MASS",
      "noi_dung": "n(Zn) = m/M = 6.5/65 = 0.1 mol."
    },
    {
      "buoc": 11,
      "chieu": "tien",
      "luat": "F_RATIO",
      "noi_dung": "n(HCl) = mức phản ứng × hệ số 2 = 0.2 mol."
    },
    {
      "buoc": 12,
      "chieu": "tien",
      "luat": "F_RATIO",
      "noi_dung": "n(ZnCl2) = mức phản ứng × hệ số 1 = 0.1 mol."
    },
    {
      "buoc": 13,
      "chieu": "tien",
      "luat": "F_RATIO",
      "noi_dung": "n(H2) = mức phản ứng × hệ số 1 = 0.1 mol."
    },
    {
      "buoc": 14,
      "chieu": "tien",
      "luat": "F_N_VOLUME",
      "noi_dung": "V(H2) = n×Vm = 0.1×22.4 = 2.24 L."
    }
  ],
  "trinh_bay": "Đầu tiên, Zn thuộc lớp đơn chất kim loại.\nTiếp theo, HCl thuộc lớp axit.\nTiếp theo, chọn được phản ứng Zn + 2HCl → ZnCl2 + H2, vì kim loại đứng trước hiđro tác dụng với axit tạo muối và hiđro. Kẽm đứng trước hiđro (mức hoạt động 7 nhỏ hơn 12), hoá trị 2.\nTiếp theo, một mol khí ở điều kiện tiêu chuẩn chiếm 22,4 lít.\nTiếp theo, khối lượng mol của Zn được tính theo 1×65, bằng 65 gam/mol.\nTiếp theo, khối lượng mol của HCl được tính theo 1×1 + 1×35,5, bằng 36,5 gam/mol.\nTiếp theo, khối lượng mol của ZnCl2 được tính theo 1×65 + 2×35,5, bằng 136 gam/mol.\nTiếp theo, khối lượng mol của H2 được tính theo 2×1, bằng 2 gam/mol.\nTiếp theo, đề bài cho khối lượng của Zn bằng 6,5 gam.\nTiếp theo, số mol của Zn bằng 6,5 gam chia cho 65 gam/mol, được 0,1 mol.\nTiếp theo, số mol của HCl bằng mức phản ứng nhân hệ số 2, được 0,2 mol.\nTiếp theo, số mol của ZnCl2 bằng mức phản ứng nhân hệ số 1, được 0,1 mol.\nTiếp theo, số mol của H2 bằng mức phản ứng nhân hệ số 1, được 0,1 mol.\nTiếp theo, thể tích khí H2 bằng 0,1 mol nhân với 22,4 lít/mol, được 2,24 lít.\nVậy, thể tích khí H2 cần tìm là 2,24 lít."
}
```

### 6.12. Thu 2,24 lít H2, tìm khối lượng ZnCl2

Đầu vào:

```json
{
  "loai": 3,
  "phan_ung": "Zn + HCl -> ZnCl2 + H2",
  "biet": [
    {
      "chat": "H2",
      "dai_luong": "V",
      "gia_tri": 2.24
    }
  ],
  "tim": {
    "chat": "ZnCl2",
    "dai_luong": "m"
  }
}
```

Đầu ra đầy đủ:

```json
{
  "co_loi_giai": true,
  "ket_qua": "13.6",
  "don_vi": "g",
  "dai_luong": "m(ZnCl2)",
  "vet": [
    {
      "buoc": 1,
      "chieu": "tien",
      "luat": "R1",
      "noi_dung": "Kiểm tra Zn: R1 xếp vào lớp Đơn chất kim loại. Thành phần ['Zn']."
    },
    {
      "buoc": 2,
      "chieu": "tien",
      "luat": "R1",
      "noi_dung": "Kiểm tra HCl: R1 xếp vào lớp Axit. Thành phần ['H', 'Cl']."
    },
    {
      "buoc": 3,
      "chieu": "tien",
      "luat": "R1",
      "noi_dung": "Kiểm tra ZnCl2: R1 xếp vào lớp Muối trung hoà. Thành phần ['Zn', 'Cl2']."
    },
    {
      "buoc": 4,
      "chieu": "tien",
      "luat": "R1",
      "noi_dung": "Kiểm tra H2: R1 xếp vào lớp Đơn chất phi kim. Thành phần ['H2']."
    },
    {
      "buoc": 5,
      "chieu": "tien",
      "luat": "BAO_TOAN",
      "noi_dung": "Cân bằng phương trình đề cho: Zn + 2HCl → ZnCl2 + H2."
    },
    {
      "buoc": 6,
      "chieu": "tien",
      "luat": "C_VM",
      "noi_dung": "Thể tích mol khí ở đktc Vm = 22.4 L/mol."
    },
    {
      "buoc": 7,
      "chieu": "tien",
      "luat": "F_MOL_MASS",
      "noi_dung": "M(Zn) = 1×65 = 65 g/mol."
    },
    {
      "buoc": 8,
      "chieu": "tien",
      "luat": "F_MOL_MASS",
      "noi_dung": "M(HCl) = 1×1 + 1×35.5 = 36.5 g/mol."
    },
    {
      "buoc": 9,
      "chieu": "tien",
      "luat": "F_MOL_MASS",
      "noi_dung": "M(ZnCl2) = 1×65 + 2×35.5 = 136 g/mol."
    },
    {
      "buoc": 10,
      "chieu": "tien",
      "luat": "F_MOL_MASS",
      "noi_dung": "M(H2) = 2×1 = 2 g/mol."
    },
    {
      "buoc": 11,
      "chieu": "tien",
      "luat": "DE_BAI",
      "noi_dung": "Giả thiết: V(H2) = 2.24 L."
    },
    {
      "buoc": 12,
      "chieu": "tien",
      "luat": "F_N_VOLUME",
      "noi_dung": "n(H2) = V/Vm = 2.24/22.4 = 0.1 mol."
    },
    {
      "buoc": 13,
      "chieu": "tien",
      "luat": "F_RATIO",
      "noi_dung": "Mức phản ứng lấy theo sản phẩm đã biết (H2) = 0.1 mol."
    },
    {
      "buoc": 14,
      "chieu": "tien",
      "luat": "F_RATIO",
      "noi_dung": "n(Zn) = mức phản ứng × hệ số 1 = 0.1 mol."
    },
    {
      "buoc": 15,
      "chieu": "tien",
      "luat": "F_RATIO",
      "noi_dung": "n(HCl) = mức phản ứng × hệ số 2 = 0.2 mol."
    },
    {
      "buoc": 16,
      "chieu": "tien",
      "luat": "F_RATIO",
      "noi_dung": "n(ZnCl2) = mức phản ứng × hệ số 1 = 0.1 mol."
    },
    {
      "buoc": 17,
      "chieu": "tien",
      "luat": "F_N_MASS",
      "noi_dung": "m(ZnCl2) = n×M = 0.1×136 = 13.6 g."
    }
  ],
  "trinh_bay": "Đầu tiên, Zn thuộc lớp đơn chất kim loại.\nTiếp theo, HCl thuộc lớp axit.\nTiếp theo, ZnCl2 thuộc lớp muối trung hoà.\nTiếp theo, H2 thuộc lớp đơn chất phi kim.\nTiếp theo, phương trình trong đề được cân bằng thành Zn + 2HCl → ZnCl2 + H2.\nTiếp theo, một mol khí ở điều kiện tiêu chuẩn chiếm 22,4 lít.\nTiếp theo, khối lượng mol của Zn được tính theo 1×65, bằng 65 gam/mol.\nTiếp theo, khối lượng mol của HCl được tính theo 1×1 + 1×35,5, bằng 36,5 gam/mol.\nTiếp theo, khối lượng mol của ZnCl2 được tính theo 1×65 + 2×35,5, bằng 136 gam/mol.\nTiếp theo, khối lượng mol của H2 được tính theo 2×1, bằng 2 gam/mol.\nTiếp theo, đề bài cho thể tích khí H2 bằng 2,24 lít.\nTiếp theo, số mol khí H2 bằng 2,24 lít chia cho 22,4 lít/mol, được 0,1 mol.\nTiếp theo, mức phản ứng lấy theo sản phẩm đã biết là H2, bằng 0,1 mol.\nTiếp theo, số mol của Zn bằng mức phản ứng nhân hệ số 1, được 0,1 mol.\nTiếp theo, số mol của HCl bằng mức phản ứng nhân hệ số 2, được 0,2 mol.\nTiếp theo, số mol của ZnCl2 bằng mức phản ứng nhân hệ số 1, được 0,1 mol.\nTiếp theo, khối lượng của ZnCl2 bằng 0,1 mol nhân với 136 gam/mol, được 13,6 gam.\nVậy, khối lượng của ZnCl2 cần tìm là 13,6 gam."
}
```

### 6.13. 0,2 mol Zn và 0,1 mol HCl, tìm số mol H2

Đầu vào:

```json
{
  "loai": 3,
  "phan_ung": "Zn + HCl -> ZnCl2 + H2",
  "biet": [
    {
      "chat": "Zn",
      "dai_luong": "n",
      "gia_tri": 0.2
    },
    {
      "chat": "HCl",
      "dai_luong": "n",
      "gia_tri": 0.1
    }
  ],
  "tim": {
    "chat": "H2",
    "dai_luong": "n"
  }
}
```

Đầu ra đầy đủ:

```json
{
  "co_loi_giai": true,
  "ket_qua": "0.05",
  "don_vi": "mol",
  "dai_luong": "n(H2)",
  "vet": [
    {
      "buoc": 1,
      "chieu": "tien",
      "luat": "R1",
      "noi_dung": "Kiểm tra Zn: R1 xếp vào lớp Đơn chất kim loại. Thành phần ['Zn']."
    },
    {
      "buoc": 2,
      "chieu": "tien",
      "luat": "R1",
      "noi_dung": "Kiểm tra HCl: R1 xếp vào lớp Axit. Thành phần ['H', 'Cl']."
    },
    {
      "buoc": 3,
      "chieu": "tien",
      "luat": "R1",
      "noi_dung": "Kiểm tra ZnCl2: R1 xếp vào lớp Muối trung hoà. Thành phần ['Zn', 'Cl2']."
    },
    {
      "buoc": 4,
      "chieu": "tien",
      "luat": "R1",
      "noi_dung": "Kiểm tra H2: R1 xếp vào lớp Đơn chất phi kim. Thành phần ['H2']."
    },
    {
      "buoc": 5,
      "chieu": "tien",
      "luat": "BAO_TOAN",
      "noi_dung": "Cân bằng phương trình đề cho: Zn + 2HCl → ZnCl2 + H2."
    },
    {
      "buoc": 6,
      "chieu": "tien",
      "luat": "C_VM",
      "noi_dung": "Thể tích mol khí ở đktc Vm = 22.4 L/mol."
    },
    {
      "buoc": 7,
      "chieu": "tien",
      "luat": "F_MOL_MASS",
      "noi_dung": "M(Zn) = 1×65 = 65 g/mol."
    },
    {
      "buoc": 8,
      "chieu": "tien",
      "luat": "F_MOL_MASS",
      "noi_dung": "M(HCl) = 1×1 + 1×35.5 = 36.5 g/mol."
    },
    {
      "buoc": 9,
      "chieu": "tien",
      "luat": "F_MOL_MASS",
      "noi_dung": "M(ZnCl2) = 1×65 + 2×35.5 = 136 g/mol."
    },
    {
      "buoc": 10,
      "chieu": "tien",
      "luat": "F_MOL_MASS",
      "noi_dung": "M(H2) = 2×1 = 2 g/mol."
    },
    {
      "buoc": 11,
      "chieu": "tien",
      "luat": "DE_BAI",
      "noi_dung": "Giả thiết: n(Zn) = 0.2 mol."
    },
    {
      "buoc": 12,
      "chieu": "tien",
      "luat": "DE_BAI",
      "noi_dung": "Giả thiết: n(HCl) = 0.1 mol."
    },
    {
      "buoc": 13,
      "chieu": "tien",
      "luat": "F_RATIO",
      "noi_dung": "Có số mol của nhiều chất tham gia. Mức phản ứng lấy theo chất hết trước: HCl. Mức phản ứng = 0.05 mol."
    },
    {
      "buoc": 14,
      "chieu": "tien",
      "luat": "F_RATIO",
      "noi_dung": "Zn dư: đề cho 0.2 mol, phản ứng dùng 0.05 mol."
    },
    {
      "buoc": 15,
      "chieu": "tien",
      "luat": "F_RATIO",
      "noi_dung": "n(ZnCl2) = mức phản ứng × hệ số 1 = 0.05 mol."
    },
    {
      "buoc": 16,
      "chieu": "tien",
      "luat": "F_RATIO",
      "noi_dung": "n(H2) = mức phản ứng × hệ số 1 = 0.05 mol."
    }
  ],
  "trinh_bay": "Đầu tiên, Zn thuộc lớp đơn chất kim loại.\nTiếp theo, HCl thuộc lớp axit.\nTiếp theo, ZnCl2 thuộc lớp muối trung hoà.\nTiếp theo, H2 thuộc lớp đơn chất phi kim.\nTiếp theo, phương trình trong đề được cân bằng thành Zn + 2HCl → ZnCl2 + H2.\nTiếp theo, một mol khí ở điều kiện tiêu chuẩn chiếm 22,4 lít.\nTiếp theo, khối lượng mol của Zn được tính theo 1×65, bằng 65 gam/mol.\nTiếp theo, khối lượng mol của HCl được tính theo 1×1 + 1×35,5, bằng 36,5 gam/mol.\nTiếp theo, khối lượng mol của ZnCl2 được tính theo 1×65 + 2×35,5, bằng 136 gam/mol.\nTiếp theo, khối lượng mol của H2 được tính theo 2×1, bằng 2 gam/mol.\nTiếp theo, đề bài cho số mol của Zn bằng 0,2 mol.\nTiếp theo, đề bài cho số mol của HCl bằng 0,1 mol.\nTiếp theo, so sánh các chất tham gia thì HCl hết trước, mức phản ứng là 0,05 mol.\nTiếp theo, Zn còn dư, vì đề cho 0,2 mol trong khi phản ứng chỉ dùng 0,05 mol.\nTiếp theo, số mol của ZnCl2 bằng mức phản ứng nhân hệ số 1, được 0,05 mol.\nTiếp theo, số mol của H2 bằng mức phản ứng nhân hệ số 1, được 0,05 mol.\nVậy, số mol của H2 cần tìm là 0,05 mol."
}
```

### 6.14. Dữ kiện mâu thuẫn: 0,1 mol HCl nhưng thu 0,1 mol H2

Đầu vào:

```json
{
  "loai": 3,
  "phan_ung": "Zn + HCl -> ZnCl2 + H2",
  "biet": [
    {
      "chat": "HCl",
      "dai_luong": "n",
      "gia_tri": 0.1
    },
    {
      "chat": "H2",
      "dai_luong": "n",
      "gia_tri": 0.1
    }
  ],
  "tim": {
    "chat": "ZnCl2",
    "dai_luong": "n"
  }
}
```

Đầu ra đầy đủ:

```json
{
  "co_loi_giai": false,
  "thong_bao": "Số mol sản phẩm đòi mức phản ứng lớn hơn chất tham gia hết trước, dữ kiện không khớp.",
  "vet": [
    {
      "buoc": 1,
      "chieu": "tien",
      "luat": "R1",
      "noi_dung": "Kiểm tra Zn: R1 xếp vào lớp Đơn chất kim loại. Thành phần ['Zn']."
    },
    {
      "buoc": 2,
      "chieu": "tien",
      "luat": "R1",
      "noi_dung": "Kiểm tra HCl: R1 xếp vào lớp Axit. Thành phần ['H', 'Cl']."
    },
    {
      "buoc": 3,
      "chieu": "tien",
      "luat": "R1",
      "noi_dung": "Kiểm tra ZnCl2: R1 xếp vào lớp Muối trung hoà. Thành phần ['Zn', 'Cl2']."
    },
    {
      "buoc": 4,
      "chieu": "tien",
      "luat": "R1",
      "noi_dung": "Kiểm tra H2: R1 xếp vào lớp Đơn chất phi kim. Thành phần ['H2']."
    },
    {
      "buoc": 5,
      "chieu": "tien",
      "luat": "BAO_TOAN",
      "noi_dung": "Cân bằng phương trình đề cho: Zn + 2HCl → ZnCl2 + H2."
    },
    {
      "buoc": 6,
      "chieu": "tien",
      "luat": "C_VM",
      "noi_dung": "Thể tích mol khí ở đktc Vm = 22.4 L/mol."
    },
    {
      "buoc": 7,
      "chieu": "tien",
      "luat": "F_MOL_MASS",
      "noi_dung": "M(Zn) = 1×65 = 65 g/mol."
    },
    {
      "buoc": 8,
      "chieu": "tien",
      "luat": "F_MOL_MASS",
      "noi_dung": "M(HCl) = 1×1 + 1×35.5 = 36.5 g/mol."
    },
    {
      "buoc": 9,
      "chieu": "tien",
      "luat": "F_MOL_MASS",
      "noi_dung": "M(ZnCl2) = 1×65 + 2×35.5 = 136 g/mol."
    },
    {
      "buoc": 10,
      "chieu": "tien",
      "luat": "F_MOL_MASS",
      "noi_dung": "M(H2) = 2×1 = 2 g/mol."
    },
    {
      "buoc": 11,
      "chieu": "tien",
      "luat": "DE_BAI",
      "noi_dung": "Giả thiết: n(HCl) = 0.1 mol."
    },
    {
      "buoc": 12,
      "chieu": "tien",
      "luat": "DE_BAI",
      "noi_dung": "Giả thiết: n(H2) = 0.1 mol."
    },
    {
      "buoc": 13,
      "chieu": "lui",
      "luat": "F_RATIO",
      "noi_dung": "Số mol sản phẩm đòi mức phản ứng lớn hơn chất tham gia hết trước, dữ kiện không khớp."
    }
  ],
  "trinh_bay": "Đầu tiên, Zn thuộc lớp đơn chất kim loại.\nTiếp theo, HCl thuộc lớp axit.\nTiếp theo, ZnCl2 thuộc lớp muối trung hoà.\nTiếp theo, H2 thuộc lớp đơn chất phi kim.\nTiếp theo, phương trình trong đề được cân bằng thành Zn + 2HCl → ZnCl2 + H2.\nTiếp theo, một mol khí ở điều kiện tiêu chuẩn chiếm 22,4 lít.\nTiếp theo, khối lượng mol của Zn được tính theo 1×65, bằng 65 gam/mol.\nTiếp theo, khối lượng mol của HCl được tính theo 1×1 + 1×35,5, bằng 36,5 gam/mol.\nTiếp theo, khối lượng mol của ZnCl2 được tính theo 1×65 + 2×35,5, bằng 136 gam/mol.\nTiếp theo, khối lượng mol của H2 được tính theo 2×1, bằng 2 gam/mol.\nTiếp theo, đề bài cho số mol của HCl bằng 0,1 mol.\nTiếp theo, đề bài cho số mol của H2 bằng 0,1 mol.\nVậy, số mol sản phẩm đòi mức phản ứng lớn hơn chất tham gia hết trước, nên dữ kiện không khớp."
}
```

## 7. Kết quả thực nghiệm

Ngày 3/11/2026 đã chạy 40 bài mỗi dạng, tổng 120 bài. Máy giải bằng suy diễn trên luật hiện có. Đối chiếu theo chương trình THCS, điều kiện tiêu chuẩn, Vm = 22,4 lít/mol và các khối lượng nguyên tử đã nêu ở mục 3.1.

Cách chấm:

- Dạng 1 đúng khi hệ số là số nguyên dương nhỏ nhất và mọi nguyên tố được bảo toàn. Sơ đồ thiếu nguyên tố phải bị từ chối.
- Dạng 2 đúng khi chuỗi nối được bằng phản ứng trong phạm vi, hoặc từ chối đúng bài không có đường. Bốn bài dùng chế độ chỉ chất cho trước.
- Dạng 3 đúng khi trị số và đơn vị khớp phép tính. Bài dữ kiện mâu thuẫn phải bị từ chối.

| Dạng | Đúng | Sai |
| --- | ---: | ---: |
| Cân bằng phương trình | 40 | 0 |
| Chuỗi phản ứng | 40 | 0 |
| Tính lượng chất | 40 | 0 |
| Cả ba dạng | 120 | 0 |

Tỉ lệ đúng là 120/120. Không có bài sai trong đợt này.

Các bài đại diện dưới đây có bản trả về đầy đủ ở mục 6, gồm cả vết suy diễn và lời giải tiếng Việt.

| Dạng | Đề | Mục | Kết quả chốt trong đầu ra |
| --- | --- | --- | --- |
| 1 | Al2O3 + HCl → AlCl3 + H2O | 6.1 | Al2O3 + 6HCl → 2AlCl3 + 3H2O |
| 1 | H2O → H2 + NaCl | 6.2 | Từ chối, không có bộ hệ số dương |
| 1 | Fe3O4 + HCl → FeCl2 + FeCl3 + H2O | 6.3 | Fe3O4 + 8HCl → FeCl2 + 2FeCl3 + 4H2O |
| 2 | S → H2SO4 | 6.4 | Ba bước qua SO2 và SO3 |
| 2 | NaCl → Na | 6.5 | Điện phân nóng chảy |
| 2 | NaCl → Cl2 | 6.6 | Cùng phản ứng điện phân, clo là sản phẩm |
| 2 | Cu → Cu(OH)2, chỉ O2, HCl, NaOH | 6.7 | Cu → CuO → CuCl2 → Cu(OH)2 |
| 2 | Al2O3 → Al | 6.8 | Qua AlCl3, magiê đẩy nhôm |
| 2 | Ag → Na | 6.9 | Không có đường |
| 2 | H2O → Na | 6.10 | Không có đường |
| 3 | 6,5 gam Zn với HCl, tìm V(H2) | 6.11 | 2,24 lít trong `trinh_bay`; `ket_qua` là 2.24, đơn vị L |
| 3 | Thu 2,24 lít H2, tìm m(ZnCl2) | 6.12 | 13,6 gam |
| 3 | 0,2 mol Zn và 0,1 mol HCl, tìm n(H2) | 6.13 | 0,05 mol, HCl hết trước |
| 3 | 0,1 mol HCl nhưng thu 0,1 mol H2 | 6.14 | Từ chối vì dữ kiện không khớp |

Đợt thực nghiệm kiểm tra trị số, phương trình và việc nhận đúng bài vô nghiệm. Lời giải tiếng Việt được kiểm tra trên các tình huống tương ứng: câu mở, câu bảo toàn, câu chốt có phương trình, câu chốt có 2,24 lít và 13,6 gam, và câu từ chối khi không có chuỗi.

## 8. Kết luận

Hệ thống tách ba việc: lưu tri thức, suy diễn, và viết lời giải.

Tri thức được tổ chức theo nguyên tố, hợp chất, điều kiện và ba lớp luật. R1 xếp lớp và tính độ tan. R2 mô tả phản ứng theo lớp, kèm những chất không tham gia; 438 phương trình cụ thể chỉ xuất hiện khi máy áp luật. R3 là các quan hệ lượng chất, dùng được theo cả hai chiều. Cách tổ chức này giữ cho đáp án của một bài không nằm sẵn trong cơ sở.

Bộ suy diễn dùng bảo toàn nguyên tố cho dạng 1, suy diễn lùi theo chiều rộng cho dạng 2, và suy diễn tiến trên công thức cho dạng 3. Chuỗi điều chế bị ràng buộc bởi độ sâu 5 bước, bởi việc chuyển tiếp nguyên tố đặc trưng, và bởi chế độ thuốc thử. Nhờ đó sản phẩm phụ như nước không bị dùng làm cầu nối.

Lớp trình bày đứng sau suy diễn. Mẫu câu có chỗ trống được chọn theo từng bước và theo trường hợp của cả bài, rồi nối bằng “Đầu tiên”, “Tiếp theo” và “Vậy”. Người đọc nhận một bài giải tiếng Việt; phần kiểm tra vẫn nhận phương trình, chuỗi và trị số.

Thực nghiệm 120 bài, mỗi dạng 40 bài, cho kết quả 120/120 theo cách chấm của chương trình THCS.

Hạn chế cần ghi cùng kết luận: đầu vào còn là dữ liệu có cấu trúc, chưa phải câu đề tự do; chuỗi dài nhất năm bước và là một dòng chuyển hoá; điện phân dung dịch có trong từ điển điều kiện nhưng chưa có luật riêng, nên nhôm từ Al2O3 đi theo con đường magiê đẩy nhôm khỏi muối; một số điều kiện như ánh sáng và áp suất chưa gắn vào luật nào. Hướng mở tự nhiên là thêm hợp chất, thêm luật lớp theo cùng lược đồ, và gắn các điều kiện đang để sẵn, mà không cần lưu đáp án của từng bài.
