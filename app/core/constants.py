"""Hằng số của mô hình K = (E, C, R, L, Cond, H) mở rộng thêm công thức và thuốc thử."""

ELEMENT_TYPES = ("kim_loai", "phi_kim", "khi_hiem")
ELEMENT_TYPE_LABELS = {
    "kim_loai": "Kim loại",
    "phi_kim": "Phi kim",
    "khi_hiem": "Khí hiếm",
}

# Dãy hoạt động SGK: số nhỏ hơn là hoạt động mạnh hơn.
ACTIVITY_SERIES = [
    "K", "Ba", "Ca", "Na", "Mg", "Al", "Zn", "Fe", "Ni", "Sn", "Pb",
    "H", "Cu", "Hg", "Ag", "Pt", "Au",
]

COMPOUND_CLASSES = (
    "don_chat_kim_loai",
    "don_chat_phi_kim",
    "don_chat_khi_hiem",
    "oxit_bazo",
    "oxit_axit",
    "oxit_luong_tinh",
    "oxit_trung_tinh",
    "axit",
    "bazo_tan",
    "bazo_khong_tan",
    "muoi_trung_hoa",
    "muoi_axit",
    "hidrua_kim_loai",
    "hop_chat_khac",
)

CLASS_LABELS = {
    "don_chat_kim_loai": "Đơn chất kim loại",
    "don_chat_phi_kim": "Đơn chất phi kim",
    "don_chat_khi_hiem": "Đơn chất khí hiếm",
    "oxit_bazo": "Oxit bazơ",
    "oxit_axit": "Oxit axit",
    "oxit_luong_tinh": "Oxit lưỡng tính",
    "oxit_trung_tinh": "Oxit trung tính",
    "axit": "Axit",
    "bazo_tan": "Bazơ tan",
    "bazo_khong_tan": "Bazơ không tan",
    "muoi_trung_hoa": "Muối trung hòa",
    "muoi_axit": "Muối axit",
    "hidrua_kim_loai": "Hiđrua kim loại",
    "hop_chat_khac": "Hợp chất khác",
}

CLASS_ONTOLOGY = {
    "don_chat_kim_loai": ["chat", "don_chat", "don_chat_kim_loai"],
    "don_chat_phi_kim": ["chat", "don_chat", "don_chat_phi_kim"],
    "don_chat_khi_hiem": ["chat", "don_chat", "don_chat_khi_hiem"],
    "oxit_bazo": ["chat", "hop_chat", "oxit", "oxit_bazo"],
    "oxit_axit": ["chat", "hop_chat", "oxit", "oxit_axit"],
    "oxit_luong_tinh": ["chat", "hop_chat", "oxit", "oxit_luong_tinh"],
    "oxit_trung_tinh": ["chat", "hop_chat", "oxit", "oxit_trung_tinh"],
    "axit": ["chat", "hop_chat", "axit"],
    "bazo_tan": ["chat", "hop_chat", "bazo", "bazo_tan"],
    "bazo_khong_tan": ["chat", "hop_chat", "bazo", "bazo_khong_tan"],
    "muoi_trung_hoa": ["chat", "hop_chat", "muoi", "muoi_trung_hoa"],
    "muoi_axit": ["chat", "hop_chat", "muoi", "muoi_axit"],
    "hidrua_kim_loai": ["chat", "hop_chat", "hidrua_kim_loai"],
    "hop_chat_khac": ["chat", "hop_chat", "hop_chat_khac"],
}

STATES = ("ran", "long", "khi", "dung_dich")
STATE_LABELS = {
    "ran": "Rắn",
    "long": "Lỏng",
    "khi": "Khí",
    "dung_dich": "Dung dịch",
}

SOLUBILITIES = ("tan", "it_tan", "khong_tan", "phan_ung_nuoc", "chua_ro")
SOLUBILITY_LABELS = {
    "tan": "Tan",
    "it_tan": "Ít tan",
    "khong_tan": "Không tan",
    "phan_ung_nuoc": "Phản ứng với nước",
    "chua_ro": "Chưa rõ",
}

REACTION_TYPES = (
    "hoa_hop",
    "phan_huy",
    "the",
    "trao_doi",
    "trung_hoa",
    "oxi_hoa_khu",
    "dien_phan",
    "khac",
)
REACTION_TYPE_LABELS = {
    "hoa_hop": "Hóa hợp",
    "phan_huy": "Phân hủy",
    "the": "Thế",
    "trao_doi": "Trao đổi",
    "trung_hoa": "Trung hòa",
    "oxi_hoa_khu": "Oxi hóa - khử",
    "dien_phan": "Điện phân",
    "khac": "Khác",
}

# Khí thường đo thể tích ở đktc trong bài toán THPT.
GAS_FORMULAS = {
    "H2", "O2", "N2", "Cl2", "F2", "CO", "CO2", "SO2", "SO3",
    "NO", "NO2", "NH3", "H2S", "HCl",
}

MOLAR_VOLUME_STP = "22.4"

ALKALI_METALS = {"Li", "Na", "K", "Rb", "Cs", "Fr"}
ALKALINE_EARTH = {"Be", "Mg", "Ca", "Sr", "Ba", "Ra"}
