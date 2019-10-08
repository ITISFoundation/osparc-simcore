const utils = require("./utils")

class ResponsesQueue {
  constructor(page) {
    this.__page = page;
    this.__queue = [];
  }

  addResponseListener(url) {
    const page = this.__page;
    const queue = this.__queue;
    queue.push(url);
    page.on("response", function callback(resp) {
      if (resp.url().includes(url)) {
        console.log("-- Queued response received", resp.url());
        page.removeListener("response", callback);
        const index = queue.indexOf(url);
        if (index > -1) {
          queue.splice(index, 1);
        }
      }
    });
  }

  isResponseInQueue(url) {
    return this.__queue.includes(url);
  }

  async waitUntilResponse(url) {
    while (this.isResponseInQueue(url)) {
      await utils.sleep(200);
    }
  }
}

module.exports = {
  ResponsesQueue
}
