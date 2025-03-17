import {
  checkUrl,
  checkMetadata,
  registerAndLogOut,
  startupCalls,
} from './tests'

describe('Sequentially run tests', () => {
  checkUrl();
  checkMetadata();
  registerAndLogOut();
  startupCalls();
});
