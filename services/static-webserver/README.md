# static-webserver

Used for static content serving.

## Further steps

In the future will fully serve all static content. Currently the `webserver` is
still serving the following routes:

- `/` resolves to a product's index.html page (osparc, tis, s4l...).
- `/static-frontend-data.json` contains information required by the frontend

## Account approvals

Product owners can choose welcome credits in USD when approving new or existing
users. Existing users receive product access without an invitation or password
change. The backend converts the selected amount using the product's credit rate;
its wallet-creation eligibility rules still apply.

Run the frontend tests from the client tests directory with `node --test`.
