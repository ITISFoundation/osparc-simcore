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
    console.log("-- Expected response added to queue", url);
    page.on("request", function callback(req) {
      if (req.url().includes(url)) {
        console.log("-- Queued request sent", req.url());
        page.removeListener("request", callback);
      }
    });
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

  __isResponseInQueue(url) {
    return this.__queue.includes(url);
  }

  async waitUntilResponse(url, timeout = 10000) {
    let sleptFor = 0;
    const sleepFor = 100;
    while (this.__isResponseInQueue(url) && sleptFor < timeout) {
      await utils.sleep(sleepFor);
      sleptFor += sleepFor;
    }
    console.log("-- Slept for", sleptFor/1000, "s waiting for", url);
    if (sleptFor >= timeout) {
      throw("-- Timeout reached." + new Date().toUTCString());
    }
  }
}

module.exports = {
  ResponsesQueue
}
