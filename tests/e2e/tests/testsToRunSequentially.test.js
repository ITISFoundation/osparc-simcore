const { checkUrl } = require('./url.js');
const { checkMetadata } = require('./title');
const { startupCalls } = require('./startupCalls');


describe('Sequentially run tests', () => {
  checkUrl();
  checkMetadata();
  startupCalls();
});
