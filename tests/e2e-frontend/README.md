# e2e tests using [playwright](https://playwright.dev/) for testing mainly the frontend against the master deployment

## Install dependencies
npm install

## Run tests
npm run tests

## Run one test
npx playwright test tests/init/statics.spec.js


## Products
Tets will run against the urls (products) defined in the products.json file

## Users
In order to provide a list of users, required for some tests, copy users.template.json to users.json and fill up the details
