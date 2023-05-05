const utils = require("./utils")

class ResponsesQueue {
  constructor(page) {
    this.__page = page;
    this.__reqQueue = [];
    this.__respPendingQueue = {};
    this.__respReceivedQueue = {};
  }

  isRequestInQueue(url) {
    return this.__reqQueue.includes(url);
  }

  isResponseInQueue(url) {
    return Object.keys(this.__respPendingQueue).includes(url);
  }

  __addRequestListener(url) {
    const reqQueue = this.__reqQueue;
    reqQueue.push(url);
    this.__respPendingQueue[url] = {};
    this.__respPendingQueue[url]["start"] = null;
    this.__respPendingQueue[url]["end"] = null;
    console.log("-- Expected response added to queue", url);
    const that = this;
    const page = this.__page;
    page.on("request", function callback(req) {
      if (req.url().includes(url)) {
        console.log("-- Queued request sent", req.method(), req.url());
        page.removeListener("request", callback);
        const index = reqQueue.indexOf(url);
        if (index > -1) {
          reqQueue.splice(index, 1);
        }
      }
      that.__respPendingQueue[url]["start"] = new Date();
    });
  }

  __addResponseListener(url, extractJsonResp = true) {
    const that = this;
    this.__page.on("response", function callback(resp) {
      if (resp.url().includes(url)) {
        console.log("-- Queued response received", resp.url(), ":");
        that.__respPendingQueue[url]["end"] = new Date();
        console.log(resp.status());
        if (resp.status() === 204) {
          that.removeResponseListener(url, "ok", callback);
        }
        else if (extractJsonResp === false && resp.status() === 200) {
          that.removeResponseListener(url, "ok", callback);
        }
        else {
          resp.json().then(data => {
            that.removeResponseListener(url, data, callback);
          });
        }
      }
    });
  }

  addResponseListener(url, extractJsonResp = true) {
    this.__addRequestListener(url);
    this.__addResponseListener(url, extractJsonResp);
  }

  removeResponseListener(url, resp, callback) {
    this.__respReceivedQueue[url] = resp;
    if (this.isResponseInQueue(url)) {
      const diff = this.__respPendingQueue[url]["end"] - this.__respPendingQueue[url]["start"];
      console.log("-- Waited", diff/1000, "s for", url);
      this.__page.removeListener("response", callback);
      delete this.__respPendingQueue[url];
    }
  }

  async waitUntilResponse(url, timeout = 20000) {
    let sleptFor = 0;
    const sleepFor = 100;
    while (this.isResponseInQueue(url) && sleptFor < timeout) {
      await utils.sleep(sleepFor);
      sleptFor += sleepFor;
    }
    if (sleptFor >= timeout) {
      throw("-- Timeout reached.");
    }
    if (Object.prototype.hasOwnProperty.call(this.__respReceivedQueue, url)) {
      const resp = this.__respReceivedQueue[url];
      if (resp && Object.prototype.hasOwnProperty.call(resp, "error") && resp["error"] !== null) {
        throw("-- Error in response", resp["error"]);
      }
      delete this.__respReceivedQueue[url];
      return resp;
    }
  }
}

module.exports = {
  ResponsesQueue
}
