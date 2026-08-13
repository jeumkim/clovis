// 배포 환경 설정.
//
// receive.html은 window.CLOVIS_API_BASE가 설정돼 있으면 그 값을,
// 아니면 "현재 호스트:8766"을 Receiver API 주소로 사용한다(로컬 실행 시
// backend/receiver를 8766번 포트로 띄우는 구성과 맞음).
//
// Render 등 클라우드에 배포하면 Receiver는 별도 서비스/도메인으로
// 뜨기 때문에 ":8766" 추정이 더 이상 맞지 않는다. 그래서 localhost가
// 아닌 호스트에서 열렸을 때만 실제 배포된 Receiver API 주소로
// 덮어쓴다. 로컬 개발(localhost/127.0.0.1)에서는 아무 영향이 없다.
//
// 배포 후 실제 Receiver 서비스 URL로 아래 값을 바꿔야 한다.
(function () {
  var isLocal = ["localhost", "127.0.0.1"].includes(location.hostname);
  if (isLocal) return;

  window.CLOVIS_API_BASE = "https://clovis-receiver.onrender.com";
})();
