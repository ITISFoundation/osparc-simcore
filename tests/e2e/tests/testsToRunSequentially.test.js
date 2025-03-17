const checkUrl = require('./url');
const checkMetadata = require('./title');
const registerAndLogOut = require('./register');
const startupCalls = require('./startupCalls');

describe('Sequentially run tests', () => {

  test('test all', () => {
    checkUrl();
    checkMetadata();
    registerAndLogOut();
    startupCalls();
  });
});
