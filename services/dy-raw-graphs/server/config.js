/* global require */
/* global __dirname */
/* global module */

const path = require('path');

module.exports = {
  // webserver configs
  HOSTNAME: '0.0.0.0',
  PORT: 4000,
  BASEPATH: '',
  APP_PATH: path.resolve(__dirname, '../raw'),
};
