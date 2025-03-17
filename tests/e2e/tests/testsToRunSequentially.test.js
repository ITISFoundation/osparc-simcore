
import { checkUrl } from './url.js';
import { checkMetadata } from './title';
import { registerAndLogOut } from './register';
import { startupCalls } from './startupCalls';


describe('Sequentially run tests', () => {
  test('test all', () => {
    checkUrl();
    checkMetadata();
    registerAndLogOut();
    startupCalls();
  });
});
