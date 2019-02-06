/* global require */
/* global process */
/* global __dirname */
/* global module */
const path = require('path');

module.exports = {
  // webserver configs
  HOSTNAME: process.env.SIMCORE_WEB_HOSTNAME || '127.0.0.1',
  PORT: process.env.SIMCORE_WEB_PORT || 8080,
  BASEPATH: process.env.SIMCORE_NODE_BASEPATH || '',
  APP_PATH: process.env.SIMCORE_WEB_OUTDIR || path.resolve(__dirname, 'source-output'),
  MODELS_PATH: '/models/',

  // S4L configs
  S4L_IP: process.env.CS_S4L_HOSTNAME || '172.16.9.89',
  S4L_PORT_APP: process.env.CS_S4L_PORT_APP || 9095,
  S4L_PORT_MOD: process.env.CS_S4L_PORT_MOD || 9096,
  S4L_DATA_PATH: 'c:/app/data/',
};
