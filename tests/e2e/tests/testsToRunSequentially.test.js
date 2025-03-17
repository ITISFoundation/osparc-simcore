import {
  checkUrl,
  checkMetadata,
  registerAndLogOut,
  startupCalls,
} from './tests'

describe('Sequentially run tests', () => {

  test('test all', () => {
    checkUrl();
    checkMetadata();
    registerAndLogOut();
    startupCalls();
  });
});
