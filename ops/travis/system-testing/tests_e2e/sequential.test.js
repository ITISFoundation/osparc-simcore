beforeAll(async () => {
  await sleep(1000);
  console.log("beforeAll");
});

afterAll(async () => {
  await sleep(1000);
  console.log("afterAll");
});

test('Sleep_0', async () => {
  await sleep(8000);
  console.log("Sleep_0");
}, 9000);

test('Sleep_1', async () => {
  await sleep(4000);
  console.log("Sleep_1");
});

test('Sleep_2', async () => {
  await sleep(2000);
  console.log("Sleep_2");
});

test('Sleep_3', async () => {
  await sleep(1000);
  console.log("Sleep_3");
});

function sleep(ms) {
  return new Promise(resolve => {
    setTimeout(resolve, ms);
  })
}
