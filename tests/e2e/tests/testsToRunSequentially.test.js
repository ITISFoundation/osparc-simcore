const { checkUrl } = require('./url.js');
const { checkMetadata } = require('./title');
const { registerAndLogOut } = require('./register');
const { startupCalls } = require('./startupCalls');


describe('Sequentially run tests', () => {
  checkUrl();
  checkMetadata();
  registerAndLogOut();
  startupCalls();
});
