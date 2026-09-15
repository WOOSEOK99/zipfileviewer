@echo off
echo Compiling ZipfileViewer.py to EXE...

:: dist 폴더는 지우지 않습니다. (다른 프로젝트 결과물 보존)
:: 빌드 시 꼬임을 유발하는 캐시(build)와 설정(spec)만 지웁니다.
if exist build rd /s /q build
if exist ZipfileViewer.spec del /f /q ZipfileViewer.spec
:: 기존에 생성되었을 수 있는 ZipfileViewer.spec 파일도 제거
if exist ZipfileViewer.spec del /f /q ZipfileViewer.spec

:: --clean: 이전 빌드 캐시 삭제
:: --onefile: 파일 하나로 통합
:: --noconsole: GUI 창 실행 시 검은색 콘솔 창 숨김
:: --name: 출력되는 EXE 파일 이름 지정
:: --add-binary: xdelta3.exe 를 EXE 내부에 번들링 (xdelta 패치 지원)
pyinstaller --clean --onefile --noconsole --name "ZipfileViewer" --add-binary "xdelta3.exe;." ZipfileViewer.py

echo.
echo Build complete. Results are in the 'dist' folder.
pause