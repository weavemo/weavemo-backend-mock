Auth 도메인은 인증과 토큰 발급/검증만 책임진다.
Users 도메인은 인증된 사용자의 데이터 관리만 책임진다.
Auth는 User의 비즈니스 필드를 수정하지 않는다.
Users는 로그인/회원가입 로직을 소유하지 않는다.
모든 보호 API는 get_current_user Depends를 통해서만 유저를 식별한다.
