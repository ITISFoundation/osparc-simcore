const schedules = {};

self.onmessage = (e) => {
  const { command, id, interval } = e.data;

  if (command === 'scheduleInterval' && id && interval) {
    if (schedules[id]) {
      clearInterval(schedules[id]);
    }
    schedules[id] = setInterval(() => {
      postMessage({ id: id, event: 'tick' });
    }, interval);
  } else if (command === 'clearInterval' && id && schedules[id]) {
    clearInterval(schedules[id]);
    delete schedules[id];
  } else {
    // do nothing here, in case of issues try logging the event here
  }
};
