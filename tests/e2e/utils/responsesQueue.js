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
        page.removeListener("response", callback);
        const index = queue.indexOf(url);
        if (index > -1) {
          queue.splice(index, 1);
        }
      }
    });
  }

  isResponseInQueue(url) {
    this.__queue.includes(url);
  }
}

module.exports = {
  ResponsesQueue
}
