"""테스트가 공유하는 코레일 응답 페이로드 샘플.

필드 이름과 모양은 실제 응답에서 온 것입니다 — 새 필드를 지어내지 마세요.
"""

from __future__ import annotations

STATION_PAYLOAD = {
    "stns": {
        "stn": [
            {
                "stn_cd": "0001",
                "stn_nm": "서울",
                "group": "1",
                "major": "1",
                "latitude": "37.55",
                "longitude": "126.97",
                "popupType": "0",
                "popupMessage": "",
            },
            {"stn_cd": "0020", "stn_nm": "부산", "group": "1", "popupType": "0", "popupMessage": ""},
            {"stn_cd": "0015", "stn_nm": "대전", "group": "1", "popupType": "0", "popupMessage": ""},
        ]
    }
}

TRAIN_INFO = {
    "h_trn_clsf_cd": "00",
    "h_trn_clsf_nm": "KTX",
    "h_trn_gp_cd": "300",
    "h_trn_no": "101",
    "h_dpt_rs_stn_nm": "서울",
    "h_dpt_rs_stn_cd": "0001",
    "h_dpt_dt": "20260401",
    "h_dpt_tm": "090000",
    "h_arv_rs_stn_nm": "부산",
    "h_arv_rs_stn_cd": "0020",
    "h_arv_dt": "20260401",
    "h_arv_tm": "123000",
    "h_run_dt": "20260401",
    "h_rsv_psb_nm": "예약가능",
    "h_spe_rsv_cd": "11",
    "h_gen_rsv_cd": "11",
    "h_wait_rsv_flg": "9",
}

SOLD_OUT_INFO = {
    **TRAIN_INFO,
    "h_trn_no": "103",
    "h_dpt_tm": "100000",
    "h_arv_tm": "133000",
    "h_rsv_psb_nm": "매진",
    "h_spe_rsv_cd": "00",
    "h_gen_rsv_cd": "00",
    "h_wait_rsv_flg": "0",
}

SEARCH_PAYLOAD = {"strResult": "SUCC", "trn_infos": {"trn_info": [TRAIN_INFO, SOLD_OUT_INFO]}}

# 인접역(``adjStnScdlOfrFlg=Y``) 조회 결과. 요청한 역이 아니라 **인근역**이 출발·도착역
# 으로 내려오는 것이 이 옵션의 전부입니다 — 별도 표시 필드는 없고 열차 한 편의 모양은
# 그대로입니다. 역 코드는 역 마스터 실측값입니다 (용산 0104 · 서대전 0025).
NEARBY_TRAIN_INFO = {
    **TRAIN_INFO,
    "h_trn_no": "451",
    "h_dpt_rs_stn_nm": "용산",
    "h_dpt_rs_stn_cd": "0104",
    "h_dpt_tm": "093000",
    "h_arv_rs_stn_nm": "서대전",
    "h_arv_rs_stn_cd": "0025",
    "h_arv_tm": "110000",
}

NEARBY_SEARCH_PAYLOAD = {
    "strResult": "SUCC",
    "trn_infos": {"trn_info": [TRAIN_INFO, NEARBY_TRAIN_INFO]},
}

RESERVATION_INFO = {
    **TRAIN_INFO,
    "h_pnr_no": "1234567890",
    "h_tot_seat_cnt": "2",
    "h_ntisu_lmt_dt": "20260325",
    "h_ntisu_lmt_tm": "143000",
    "h_rsv_amt": "119600",
}

RESERVATION_LIST_PAYLOAD = {
    "strResult": "SUCC",
    "jrny_infos": {"jrny_info": [{"train_infos": {"train_info": [RESERVATION_INFO]}}]},
}

SEAT_INFO = {
    "h_srcar_no": "3",
    "h_seat_no": "5A",
    "h_psrm_cl_nm": "일반실",
    "h_psg_tp_dv_nm": "어른",
    "h_rcvd_amt": "59800",
    "h_seat_prc": "59800",
    "h_dcnt_amt": "0",
}

SEAT_DETAIL_PAYLOAD = {
    "strResult": "SUCC",
    "h_wct_no": "0143",
    "jrny_infos": {"jrny_info": [{"seat_infos": {"seat_info": [SEAT_INFO]}}]},
}

TICKET_RAW = {
    **TRAIN_INFO,
    "h_seat_no": "5A",
    "h_seat_no_end": "5B",
    "h_seat_cnt": "2",
    "h_srcar_no": "3",
    "h_buy_ps_nm": "홍길동",
    "h_orgtk_sale_dt": "20260320",
    "h_pnr_no": "1234567890",
    "h_orgtk_wct_no": "0000",
    "h_orgtk_ret_sale_dt": "20260320",
    "h_orgtk_sale_sqno": "0001",
    "h_orgtk_ret_pwd": "1111",
    "h_rcvd_amt": "119600",
}

TICKET_LIST_PAYLOAD = {
    "strResult": "SUCC",
    "reservation_list": [{"ticket_list": [{"train_info": [TICKET_RAW]}]}],
}

# 환불 수수료 사전조회 (refunds.CommissionView). 필드 이름은 코레일톡+ 7.0.1 의
# RefundCommissionOut 에서 확인한 것입니다.
REFUND_FEE_PAYLOAD = {
    "strResult": "SUCC",
    "ret_fee": "5600",
    "ret_amt": "53400",
    "use_psb_mlg_num": "1200",
    "prg_psb_flg": "Y",
    "tk_ret_tms_dv_cd": "21",
}

TICKET_SEAT_PAYLOAD = {
    "strResult": "SUCC",
    "ticket_infos": {"ticket_info": [{"tk_seat_info": [{"h_seat_no": "7C"}]}]},
}

CIPHER_PAYLOAD = {
    "strResult": "SUCC",
    "app.login.cphd": {"idx": "7", "key": "0123456789abcdef0123456789abcdef"},
}

LOGIN_OK = {
    "strResult": "SUCC",
    "strMbCrdNo": "1234567890",
    "strCustNm": "홍길동",
    "strEmailAdr": "me@example.com",
    "strCpNo": "010-1234-5678",
}

LOGIN_FAIL = {"strResult": "FAIL", "h_msg_cd": "WRC000000", "h_msg_txt": "비밀번호가 틀렸습니다"}

NO_RESULTS = {"strResult": "FAIL", "h_msg_cd": "P100", "h_msg_txt": "결과 없음"}

OK = {"strResult": "SUCC"}
