"""테스트가 공유하는 코레일 응답 페이로드 샘플.

필드 이름과 모양은 실제 응답에서 온 것입니다 — 새 필드를 지어내지 마세요.
맨 아래의 NetFunnel 골든만 요청(헤더·params)이고, 그 밖의 값은 응답입니다.
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

#: 찾는 예약(1234567890) 하나가 다른 예약 셋 사이에 섞여 있는 목록.
#: 좌석 상세를 몇 번 조회하는지 세려면 예약이 여럿이어야 합니다.
MANY_RESERVATIONS_PAYLOAD = {
    "strResult": "SUCC",
    "jrny_infos": {
        "jrny_info": [
            {
                "train_infos": {
                    "train_info": [
                        *({**RESERVATION_INFO, "h_pnr_no": f"999999999{i}"} for i in range(3)),
                        RESERVATION_INFO,
                    ]
                }
            }
        ]
    },
}

#: 위 목록에 담긴 예약번호 — 목록 응답 순서 그대로입니다.
MANY_RESERVATION_IDS = ("9999999990", "9999999991", "9999999992", "1234567890")

#: 예매(``reserve``) 성공 응답.
RESERVE_OK = {"strResult": "SUCC", "h_pnr_no": "1234567890"}

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

#: 승인된 7.0.8 로그인 폼. 동적 암호문과 키 발급 인덱스만 정규화합니다.
LOGIN_FORM_GOLDEN = {
    "Device": "AD",
    "Version": "250722001",
    "AppVersion": "7.0.8",
    "Key": "korail1234567890",
    "txtInputFlg": "4",
    "txtMemberNo": "01012345678",
    "txtPwd": "<encrypted>",
    "checkValidPw": "Y",
    "idx": "<issued>",
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

#: ``strResult`` 는 SUCC 인데 ``app.login.cphd`` 가 덜 온 응답들. 서버가 실제로
#: 이렇게 보낸 적이 있어서가 아니라, 날 인덱싱이 KeyError 로 새는 것을 막기 위한
#: 경계 입력입니다.
PARTIAL_CIPHER_INFOS = (
    {"idx": "7"},
    {"key": "0123456789abcdef0123456789abcdef"},
    {"idx": "7", "key": ""},
    {},
    "",
)


def cipher_response(cipher_info: object) -> dict[str, object]:
    """``app.login.cphd`` 자리에 임의의 값을 끼운 ``code`` 응답."""
    return {"strResult": "SUCC", "app.login.cphd": cipher_info}


#: AES 규격(16·24·32바이트)에 안 맞는 키. pycryptodome 의 ValueError 를 부릅니다.
UNUSABLE_CIPHER_PAYLOAD = cipher_response({"idx": "7", "key": "short"})

#: ``idx`` 가 문자열이 아닌 응답. 폼에는 문자열로 나가야 합니다.
NUMERIC_IDX_CIPHER_PAYLOAD = cipher_response({"idx": 7, "key": "0123456789abcdef0123456789abcdef"})

#: 로그인은 됐는데(SUCC + 회원번호) 표시용 프로필 필드가 빠진 응답.
LOGIN_OK_WITHOUT_PROFILE = {"strResult": "SUCC", "strMbCrdNo": "1234567890"}

LOGIN_FAIL = {"strResult": "FAIL", "h_msg_cd": "WRC000000", "h_msg_txt": "비밀번호가 틀렸습니다"}

#: 같은 비밀번호를 6개월 넘게 쓴 계정의 로그인 응답. 키 구성과 코드 · 안내문은 2026-10-13
#: 실서버 응답 그대로이고 값은 예시입니다. **성공 봉투에 회원번호까지 오지만** 이름 · 이메일
#: 같은 프로필은 없고, 이 세션으로 보낸 인증 호출은 전부 P058 로 거절됐습니다.
LOGIN_PASSWORD_CHANGE_REQUIRED = {
    "strResult": "SUCC",
    "h_msg_cd": "WRC000420",
    "h_msg_txt": (
        "6개월 이상 동일한 비밀번호를 사용하고 있습니다.\n"
        "개인정보 보호를 위하여 최신 버전 업데이트 이후 비밀번호를 변경하시기 바랍니다."
    ),
    "strCustNo": "0000000000",
    "strMbCrdNo": "1234567890",
    "strRedirectUrl": "https://example.invalid/password",
}

NO_RESULTS = {"strResult": "FAIL", "h_msg_cd": "P100", "h_msg_txt": "결과 없음"}

OK = {"strResult": "SUCC"}

#: HTTP 403 과 함께 온 이용제한 응답 (이슈 #27 의 실서버 보고). 코레일 형식이 아니라
#: ``code``·``id``·``message`` 세 필드뿐입니다. ``id`` 는 보고자가 가린 값이라 자리표시자이고,
#: ``code`` 는 보고에서 문자열로 옮겨 적은 것이라 원래 타입(숫자/문자열)은 확인하지 못했습니다.
ACCESS_RESTRICTED = {
    "code": "-2000",
    "id": "redacted-trace-id",
    "message": (
        "원활한 서비스를 위해 안정적인 환경에서 앱을 이용해 주시기 바랍니다. "
        "매크로 등 미허가 도구 사용 시 이용이 제한될 수 있습니다."
        "정상적인 환경임에도 이용이 제한되는 경우 앱을 완전히 종료한 후 다시 실행해 주시기 바랍니다."
    ),
}

# ---------------------------------------------------------------- 공항버스
# 필드 이름은 코레일+ 7.0.8 의 응답 모델 선언 그대로이고(CommonCodeOut · ScdlQryOut ·
# ScdlQryOutTrain · TResidualSeatsResearchOut), 키 구성과 값의 **모양**은 2026-10-13 실서버
# 조회에서 본 그대로입니다 — 정류장 넷, 0 을 채운 편 번호 · 좌석 수 · 운임, 봉투의 코드.
# 시각과 남은 좌석 수는 예시입니다.

BUS_STOPS_PAYLOAD = {
    "strResult": "SUCC",
    "h_msg_cd": "API.I00000",
    "h_msg_txt": "Success",
    "loginFlg": "N",
    "app.limousine.stationNm": ["광명역", "인천공항T1", "인천공항T2", "송도국제교"],
    "app.limousine.stationCd": ["0501", "0921", "0923", "0924"],
    "app.limousine.airportBusMsg": "광명역 도심공항터미널 이용 안내",
}

#: 특실이 없어 그 칸은 음수로 옵니다. 운임은 열네 자리로 0 을 채웁니다.
BUS_INFO = {
    "trnOrdrNo": "001",
    "chtnDvCd": "1",
    "dptRsStnCd": "0501",
    "arvRsStnCd": "0921",
    "trnNo": "08008",
    "ymsAplFlg": "N",
    "trnGpCd": "980",
    "runDt": "20261016",
    "dptDt": "20261016",
    "dptTm": "060000",
    "arvDt": "20261016",
    "arvTm": "065000",
    "ocurDlayTnum": "000000",
    "gnrmRestSeatNum": "000024",
    "sprmRestSeatNum": "-00001",
    "restStndNum": "000000",
    "restFresNum": "000000",
    "stlbTrnClsfCd": "98",
    "dptStnRunOrdr": "000001",
    "arvStnRunOrdr": "000002",
    "rcvdPrc": "00000000016000",
}

FULL_BUS_INFO = {
    **BUS_INFO,
    "trnOrdrNo": "002",
    "trnNo": "08010",
    "dptTm": "063000",
    "arvTm": "072000",
    "gnrmRestSeatNum": "000000",
}

BUS_SCHEDULE_PAYLOAD = {
    "strResult": "SUCC",
    "h_msg_cd": "IRG000000",
    "h_msg_txt": "정상처리되었습니다",
    "msgCd": "IRG000000",
    "msgTxt": "정상처리되었습니다",
    "lgtmShtmDvCd": "2",
    "fllwPgExt": "N",
    "trainList": [BUS_INFO, FULL_BUS_INFO],
}

#: 편이 없는 구간의 응답 (2026-10-13 실서버). 인천공항 → 광명역처럼 코레일이 팔지 않는
#: 방향도 이 모양으로 옵니다.
NO_BUSES_PAYLOAD = {"strResult": "FAIL", "h_msg_cd": "WRG000000", "h_msg_txt": "조회 결과가 없습니다."}

#: 공항버스의 좌석 식별자와 표시는 둘 다 번호입니다("1"). 열차는 표시가 "15A" 같은 모양입니다.
BUS_SEAT_INFO = {
    "seat_no": "1",
    "seat_spec": "1",
    "sale_psb_flg": "Y",
    "dir_seat_att_cd": "009",
    "rq_seat_att_cd": "015",
    "etc_seat_att_cd": "000",
    "sqr_no": "000",
    "vz_msg_dv_cd": "",
    "intg_msg_cd": "",
    "intg_msg": "",
}

BUS_SEAT_MAP_PAYLOAD = {
    "strResult": "SUCC",
    "h_msg_cd": "IRG000000",
    "h_msg_txt": "정상처리되었습니다",
    "scar_no": "0001",
    "car_tp_cd": "10283101",
    "seat_ary_cd": "3",
    "up_dn_dv_cd": "U",
    "vrBnrUrl": "",
    "seat_total_count": 28,
    "seat_remain_count": 18,
    "windowList": [],
    "layout_type": 1,
    "seatList": [BUS_SEAT_INFO, {**BUS_SEAT_INFO, "seat_no": "2", "seat_spec": "2", "sale_psb_flg": "N"}],
}

# ---------------------------------------------------------------- 마일리지 · 할인쿠폰
# 필드 이름은 코레일+ 7.0.8 의 응답 모델 선언 그대로입니다(AmtSpecOut ·
# AmtSpecOutSpecInfo · CouponOut · CouponOutInfo).
#
# 마일리지는 값의 **모양**이 2026-10-13 실서버 조회에서 본 그대로입니다 — 잔액은 0 을 채운
# 아홉 자리(소멸 예정은 열한 자리), 쪽 수는 다섯 자리, 내역의 증감은 부호와 쉼표가 붙은
# 표시용 문자열, 봉투의 코드와 문구. 응답에 오는 키도 그때 본 구성입니다. 값 자체는 예시입니다.
#
# 쿠폰은 **쿠폰이 없는 응답**(NO_COUPONS_PAYLOAD)만 실서버에서 봤습니다. 쿠폰이 실린
# 응답(COUPON_INFO · COUPONS_PAYLOAD)의 값은 전부 예시이고 모양도 확인한 것이 아닙니다.

MILEAGE_ENTRY_INFO = {
    "rcpDvNm": "적립",
    "dptDt": "20261003",
    "mlgAcmDvCdNm": "마일리지 적립 (열차이용)",
    "stlAmt": "00000059800",
    "savePontValNum": "00000002990",
    "pontAmt": "+2,990",
    "pontDvNm": "KTX 마일리지",
}

USED_MILEAGE_ENTRY_INFO = {
    **MILEAGE_ENTRY_INFO,
    "rcpDvNm": "사용",
    "dptDt": "20260921",
    "mlgAcmDvCdNm": "코레일",
    "pontAmt": "-1,000",
}

MILEAGE_PAYLOAD = {
    "strResult": "SUCC",
    "h_msg_cd": "IRZ000001",
    "h_msg_txt": "정상적으로 조회 되었습니다.",
    "msgCd": "IRZ000001",
    "msgTxt": "정상적으로 조회 되었습니다.",
    "totAvlRailPontValNum": "000012340",
    "totAvlAfltPontValNum": "000000500",
    "totAcmRailPontValNum1": "000000000",
    "totAvlRailPontValNum1": "000000660",
    "totUseRailPontValNum1": "000000000",
    "railNowSavePontValNum1": "000000000",
    "delPontValNum": "00000000120",
    "specList": [MILEAGE_ENTRY_INFO, USED_MILEAGE_ENTRY_INFO],
    "qryCnt": "00000002",
    "pgCnt": "00003",
    "ktxMlgInfo": "철도포인트는 KTX마일리지와 동일한 방식으로 사용 가능합니다. 적립일로부터 5년간 유효합니다.",
}

COUPON_INFO = {
    "h_cpn_no": "C202610120001234",
    "h_disc_rt_amt_dv_cd": "1",
    "h_fdcert_mg_st_dt": "20261001",
    "h_fdcert_mg_cls_dt": "20261231",
    "h_inwk_prc_disc_rt_amt": "10",
    "h_wknd_prc_disc_rt_amt": "10",
    "h_inwk_fare_disc_rt_amt": "0",
    "h_wknd_fare_disc_rt_amt": "0",
    "h_rmk_1_cont": "KTX 10% 할인쿠폰",
    "h_rmk_2_cont": "주중 · 주말 모두 사용 가능",
    "h_rmk_3_cont": "KTX",
    "h_dscp_knd_cd": "01",
    "guide": "한 번에 한 장만 쓸 수 있습니다.",
}

COUPONS_PAYLOAD = {
    "strResult": "SUCC",
    "h_msg_cd": "IRZ000001",
    "h_msg_txt": "정상적으로 조회 되었습니다.",
    "h_tot_page_cnt": "1",
    "h_page_no": "1",
    "h_tot_cnt": "1",
    "h_row_cnt": "1",
    "coupon_infos": {"coupon_info": [COUPON_INFO]},
}

#: 쿠폰이 없을 때 (2026-10-13 실서버). 성공 봉투에 "결과 없음" 코드가 실리고, 목록을 싸는
#: ``coupon_infos`` · ``coupon_info`` 키는 그대로 옵니다. 그 안이 빈 목록인지 null 인지는
#: 보지 않았습니다 — 어느 쪽이든 빈 리스트로 읽습니다.
NO_COUPONS_PAYLOAD = {
    "strResult": "SUCC",
    "h_msg_cd": "WRG000000",
    "h_msg_txt": "조회 결과가 없습니다.",
    "coupon_infos": {"coupon_info": []},
}

# ---------------------------------------------------------------- 호차 · 좌석 조회
# 필드 이름은 코레일+ 7.0.8 의 응답 모델 선언 그대로이고(TrainScheduleOutTrainInfo ·
# TrainResearchOut · TrainResearchOutCarInfo · TrainResearchOutSeatInfo ·
# TResidualSeatsResearchOut · TResidualSeatsResearchOutSeat), 값의 **모양**(자릿수 채움,
# 코드 길이)은 2026-10-12 실서버 조회에서 본 그대로입니다. 값 자체는 예시입니다.

#: 호차 · 좌석 조회에 필요한 필드(운행 순서 · 좌석 속성)까지 내려온 조회 결과 한 편.
SEATABLE_TRAIN_INFO = {
    **TRAIN_INFO,
    "h_dpt_stn_run_ordr": "000001",
    "h_arv_stn_run_ordr": "000019",
    "h_dpt_stn_cons_ordr": "000001",
    "h_arv_stn_cons_ordr": "000028",
    "h_seat_att_cd": "015",
}

SEATABLE_SEARCH_PAYLOAD = {"strResult": "SUCC", "trn_infos": {"trn_info": [SEATABLE_TRAIN_INFO]}}

#: 호차 번호는 네 자리, 좌석 수는 여섯 · 다섯 자리로 0 을 채워 옵니다.
CAR_INFO = {
    "h_srcar_no": "0003",
    "h_seat_cnt": "000058",
    "h_psrm_cl_cd": "1",
    "h_psrm_cl_nm": "일반실",
    "h_rest_seat_cnt": "00019",
    "seatAttInfos": [{"seatAttCd": "015", "seatAttNm": "일반석"}],
}

#: 남은 좌석이 없는 호차. 실서버는 ``seatAttInfos`` 를 빈 목록으로 주기도 합니다.
FULL_CAR_INFO = {**CAR_INFO, "h_srcar_no": "0004", "h_rest_seat_cnt": "00000", "seatAttInfos": []}

SEAT_CARS_PAYLOAD = {
    "strResult": "SUCC",
    "h_msg_cd": "IRG000000",
    "h_msg_txt": "정상처리되었습니다",
    "h_trn_no": "00101",
    "h_trn_gp_cd": "300",
    "h_trn_clsf_cd": "00",
    "h_rcmd_srcar_no": "0003",
    "srcar_infos": {"srcar_info": [CAR_INFO, FULL_CAR_INFO]},
}

CAR_SEAT_INFO = {
    "seat_no": "57",
    "seat_spec": "15A",
    "sale_psb_flg": "Y",
    "dir_seat_att_cd": "009",
    "rq_seat_att_cd": "015",
    "etc_seat_att_cd": "000",
    "sqr_no": "000",
    "vz_msg_dv_cd": "",
    "intg_msg_cd": "",
    "intg_msg": "",
}

TAKEN_CAR_SEAT_INFO = {**CAR_SEAT_INFO, "seat_no": "58", "seat_spec": "15B", "sale_psb_flg": "N"}

SEAT_MAP_PAYLOAD = {
    "strResult": "SUCC",
    "h_msg_cd": "IRG000000",
    "h_msg_txt": "정상처리되었습니다",
    "scar_no": "0003",
    "seatList": [CAR_SEAT_INFO, TAKEN_CAR_SEAT_INFO],
}

# ---------------------------------------------------------------- 환승 조회
# 필드 이름은 코레일+ 7.0.8 의 응답 모델 선언 그대로이고(ChtnStnOut · ChtnStnOutItem,
# TrainScheduleOutTrainInfo), 값의 **모양**(여정 번호 세 자리, 구간 순서 한 자리, 환승
# 구분 코드)은 2026-10-12 실서버 조회에서 본 그대로입니다. 값 자체는 예시입니다.

#: 실서버는 영문 역 이름(``chtnRsStnEngNm``)을 빼고 주기도 합니다.
TRANSFER_STATIONS_PAYLOAD = {
    "strResult": "SUCC",
    "h_msg_cd": "IRZ000001",
    "chtnList": [
        {"chtnRsStnCd": "0015", "chtnRsStnNm": "대전", "chtnRsStnEngNm": "Daejeon"},
        {"chtnRsStnCd": "0001", "chtnRsStnNm": "서울"},
    ],
}

#: 서울 → 대전. 같은 여정의 두 행은 ``h_trn_seq`` 가 같고(``"000"`` 부터), 여정 안의
#: 타는 순서가 ``h_chg_trn_seq`` 입니다. 환승 행은 ``h_chg_trn_dv_cd`` 가 ``"2"`` 입니다.
FIRST_LEG_INFO = {
    **TRAIN_INFO,
    "h_arv_rs_stn_nm": "대전",
    "h_arv_rs_stn_cd": "0015",
    "h_arv_tm": "100000",
    "h_trn_seq": "000",
    "h_chg_trn_seq": "1",
    "h_chg_trn_dv_cd": "2",
    "h_chg_trn_dv_nm": "환승",
}

#: 대전 → 부산.
SECOND_LEG_INFO = {
    **TRAIN_INFO,
    "h_trn_clsf_cd": "02",
    "h_trn_clsf_nm": "무궁화호",
    "h_trn_no": "1201",
    "h_dpt_rs_stn_nm": "대전",
    "h_dpt_rs_stn_cd": "0015",
    "h_dpt_tm": "102000",
    "h_arv_tm": "133000",
    "h_trn_seq": "000",
    "h_chg_trn_seq": "2",
    "h_chg_trn_dv_cd": "2",
    "h_chg_trn_dv_nm": "환승",
}

#: 둘째 구간이 매진인 다음 여정.
LATER_FIRST_LEG_INFO = {
    **FIRST_LEG_INFO,
    "h_trn_no": "103",
    "h_dpt_tm": "100000",
    "h_arv_tm": "110000",
    "h_trn_seq": "001",
}
SOLD_OUT_SECOND_LEG_INFO = {
    **SECOND_LEG_INFO,
    "h_trn_no": "1203",
    "h_dpt_tm": "112000",
    "h_arv_tm": "143000",
    "h_spe_rsv_cd": "13",
    "h_gen_rsv_cd": "13",
    "h_trn_seq": "001",
}

TRANSFER_SEARCH_PAYLOAD = {
    "strResult": "SUCC",
    "h_msg_cd": "IRG000000",
    "h_next_pg_flg": "N",
    "h_rslt_cnt": "4",
    "trn_infos": {"trn_info": [FIRST_LEG_INFO, SECOND_LEG_INFO, LATER_FIRST_LEG_INFO, SOLD_OUT_SECOND_LEG_INFO]},
}

# ---------------------------------------------------------------- 환승 예약
# 예매에 필요한 구간 순서(구성 · 운행)와 좌석 속성까지 내려온 환승 구간들, 그리고 그 예매가
# 만든 예약 하나(예약번호 하나에 여정 둘). 필드 이름은 코레일+ 7.0.8 의 응답 모델 선언
# 그대로이고(TrainScheduleOutTrainInfo · ReservationViewOutTrainInfo · ReservationOutJrnyInfo ·
# ReservationOutSeatInfo), 예약 응답의 모양은 실서버에서 본 것입니다. 값은 예시입니다.

RESERVABLE_FIRST_LEG_INFO = {
    **FIRST_LEG_INFO,
    "h_dpt_stn_cons_ordr": "000001",
    "h_arv_stn_cons_ordr": "000012",
    "h_dpt_stn_run_ordr": "000001",
    "h_arv_stn_run_ordr": "000005",
    "h_seat_att_cd": "015",
}

#: 둘째 구간은 좌석 속성이 첫 구간과 다릅니다 — 구간마다 따로 실어야 하는 값입니다.
RESERVABLE_SECOND_LEG_INFO = {
    **SECOND_LEG_INFO,
    "h_dpt_stn_cons_ordr": "000012",
    "h_arv_stn_cons_ordr": "000040",
    "h_dpt_stn_run_ordr": "000007",
    "h_arv_stn_run_ordr": "000021",
    "h_seat_att_cd": "019",
}

RESERVABLE_TRANSFER_SEARCH_PAYLOAD = {
    "strResult": "SUCC",
    "trn_infos": {"trn_info": [RESERVABLE_FIRST_LEG_INFO, RESERVABLE_SECOND_LEG_INFO]},
}

#: 환승 예약의 목록 응답 — 예약번호가 같은 항목이 구간마다 하나씩, 여정 하나(jrny_info) 안에
#: 함께 옵니다. 키와 값의 **모양**은 2026-10-13 실서버 응답 그대로입니다 — 여정 번호는 네 자리,
#: 변경번호는 세 자리, 금액은 0 을 채운 열한 자리. **금액은 구간의 것이 아니라 예약 전체의
#: 금액이 두 항목에 똑같이** 실립니다. 값 자체는 예시입니다.
TRANSFER_RESERVATION_ENTRIES = [
    {
        **FIRST_LEG_INFO,
        "h_pnr_no": "1234567890",
        "h_pnr_cnt": "00000000002",
        "h_jrny_sqno": "0001",
        "h_jrny_tp_cd": "14",
        "h_tot_seat_cnt": "00001",
        "h_rsv_amt": "00000041500",
        "h_rsv_chg_no": "000",
    },
    {
        **SECOND_LEG_INFO,
        "h_pnr_no": "1234567890",
        "h_pnr_cnt": "00000000000",
        "h_jrny_sqno": "0002",
        "h_jrny_tp_cd": "14",
        "h_tot_seat_cnt": "00001",
        "h_rsv_amt": "00000041500",
        "h_rsv_chg_no": "000",
    },
]

TRANSFER_RESERVATION_LIST_PAYLOAD = {
    "strResult": "SUCC",
    "h_jrny_cnt": "2",
    "jrny_infos": {"jrny_info": [{"train_infos": {"train_info": TRANSFER_RESERVATION_ENTRIES}}]},
}

FIRST_LEG_SEAT_INFO = {**SEAT_INFO, "h_srcar_no": "3", "h_seat_no": "5A", "h_rcvd_amt": "23700", "h_seat_prc": "23700"}
#: 실서버는 호차 번호를 숫자로 주기도 합니다.
SECOND_LEG_SEAT_INFO = {**SEAT_INFO, "h_srcar_no": 2, "h_seat_no": "41", "h_rcvd_amt": "17800", "h_seat_prc": "17800"}

#: 환승 예약의 상세 응답 — 여정이 둘이고, 각자 목록과 같은 여정 번호와 그 구간의 좌석을 가집니다.
TRANSFER_SEAT_DETAIL_PAYLOAD = {
    "strResult": "SUCC",
    "h_wct_no": "0143",
    "h_jrny_cnt": "2",
    "jrny_infos": {
        "jrny_info": [
            {
                "h_jrny_sqno": "0001",
                "h_jrny_tp_cd": "14",
                "h_rsv_chg_no": "000",
                "seat_infos": {"seat_info": [FIRST_LEG_SEAT_INFO]},
            },
            {
                "h_jrny_sqno": "0002",
                "h_jrny_tp_cd": "14",
                "h_rsv_chg_no": "000",
                "seat_infos": {"seat_info": [SECOND_LEG_SEAT_INFO]},
            },
        ]
    },
}

# ---------------------------------------------------------------- 운임 조회
# 필드 이름은 코레일+ 7.0.8 의 응답 모델 선언 그대로이고 (PrcFareOut · PrcFareOutItem),
# 값의 **모양**(금액의 쉼표와 ``원``, 해당 없는 칸의 ``-``, 네 자리 구간 번호, 0 을 채우지
# 않은 열차번호, 봉투의 코드)은 2026-10-13 실서버 조회에서 본 그대로입니다. 값 자체는 예시입니다.

#: 일반실에는 요금이 없어 그 칸이 ``-`` 로 옵니다.
GENERAL_FARE_INFO = {
    "trnNo": "101",
    "jrnySqno": "0001",
    "psrmClNm": "일반실",
    "rcvdPrc": "59,800원",
    "rcvdFare": "-",
    "sumAmt": "59,800원",
}

SPECIAL_FARE_INFO = {**GENERAL_FARE_INFO, "psrmClNm": "특실", "rcvdFare": "23,900원", "sumAmt": "83,700원"}

FARE_PAYLOAD = {
    "strResult": "SUCC",
    "h_msg_cd": "API.I00000",
    "h_msg_txt": "Success",
    "prcList": [GENERAL_FARE_INFO, SPECIAL_FARE_INFO],
}

#: 환승 여정의 응답. 구간마다 줄이 나뉘고, **객실 순으로 먼저** 묶여 옵니다 (일반실 두 구간,
#: 그다음 상위 객실 두 구간). 상위 객실의 이름은 열차에 따라 다릅니다.
TRANSFER_FARE_PAYLOAD = {
    "strResult": "SUCC",
    "h_msg_cd": "API.I00000",
    "h_msg_txt": "Success",
    "prcList": [
        {**GENERAL_FARE_INFO, "rcvdPrc": "23,700원", "sumAmt": "23,700원"},
        {**GENERAL_FARE_INFO, "trnNo": "1201", "jrnySqno": "0002", "rcvdPrc": "17,800원", "sumAmt": "17,800원"},
        {**SPECIAL_FARE_INFO, "rcvdPrc": "23,700원", "rcvdFare": "9,500원", "sumAmt": "33,200원"},
        {
            **SPECIAL_FARE_INFO,
            "trnNo": "1201",
            "jrnySqno": "0002",
            "psrmClNm": "우등실",
            "rcvdPrc": "17,800원",
            "rcvdFare": "5,500원",
            "sumAmt": "23,300원",
        },
    ],
}

#: NetFunnel 대기열 게이트에 실려 나가는 헤더. 이 값이 바뀌면 코레일 앞단이 거절합니다.
NETFUNNEL_HEADERS_GOLDEN = {
    "Host": "nf.letskorail.com",
    "Connection": "Keep-Alive",
    "User-Agent": "Apache-HttpClient/UNAVAILABLE (java 1.4)",
}

#: 대기 → 대기 → 통과 → 완료 흐름에서 나가야 하는 요청 순서(url + params).
#: opcode 순서(5101 → 5002 → 5004)와 sid·aid·key·ttl 이 하나라도 달라지면 대기열을
#: 통과하지 못합니다. 동기판과 비동기판이 **같은** 이 값을 만족해야 합니다.
NETFUNNEL_CALLS_GOLDEN = [
    {"url": "http://nf.letskorail.com/ts.wseq", "params": {"opcode": "5101", "sid": "service_1", "aid": "act_8"}},
    {
        "url": "http://nf.letskorail.com/ts.wseq",
        "params": {"opcode": "5002", "sid": "service_1", "aid": "act_8", "key": "TICKET-1", "ttl": "1"},
    },
    {
        "url": "http://nf.letskorail.com/ts.wseq",
        "params": {"opcode": "5002", "sid": "service_1", "aid": "act_8", "key": "TICKET-1", "ttl": "1"},
    },
    {"url": "http://nf.letskorail.com/ts.wseq", "params": {"opcode": "5004", "key": "TICKET-1"}},
]
