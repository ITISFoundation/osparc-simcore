onmessage = e => {
  const action = e.data[0];
  switch (action) {
    case "start": {
      if (this.__timer) {
        clearInterval(this.__timer);
      }
      const newInterval = e.data[1];
      this.__timer = setInterval(() => {
        postMessage("interval");
      }, newInterval);
      break;
    }
    case "stop":
      if (this.__timer) {
        clearInterval(this.__timer);
      }
      break;
  }
};
