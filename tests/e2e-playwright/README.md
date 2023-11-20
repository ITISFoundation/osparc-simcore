`pytest -s test sim4life.py --tracing on --headed `

`pytest -s tests/sim4life.py --tracing on --html=report.html --browser chromium --browser firefox`

`playwright show-trace test-results/tests-sim4life-py-test-billable-sim4life-chromium/trace.zip`

`PWDEBUG=1 pytest --s tests/sim4life.py`

`playwright codegen sim4life.io`



INSTALATION (when you want to use --browser webkit, still now fully working locally):
`sudo apt-get install -y libappindicator-dev`

`sudo apt-get install -y gstreamer1.0-libav libnss3-tools libatk-bridge2.0-0 libcups2-dev libxkbcommon-x11-0 libxcomposite-dev libxrandr2 libgbm-dev libgtk-3-0`

`sudo apt-get install -y libsoup-3.0`

```
sudo apt update
sudo apt upgrade
sudo apt update
sudo apt-get install libgles2
sudo apt-get install gstreamer1.0-libav
sudo apt-get install libharfbuzz-icu0
sudo apt-get install libwoff1
sudo apt-get install libgstreamer-plugins-bad1.0-0
sudo apt-get install libgstreamer-gl1.0-0
sudo apt-get install libwebp-dev
```
