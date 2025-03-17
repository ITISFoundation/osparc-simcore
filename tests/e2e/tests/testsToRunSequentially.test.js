
import { checkUrl } from './url.js';
import { checkMetadata } from './title';
import { registerAndLogOut } from './register';
import { startupCalls } from './startupCalls';


describe('Sequentially run tests', () => {
  checkUrl();
  checkMetadata();
  registerAndLogOut();
  startupCalls();
});
