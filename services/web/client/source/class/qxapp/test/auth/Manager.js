/**
 *
 */
qx.Class.define("qxapp.test.auth.Manager", {
  extend: qx.dev.unit.TestCase,
  include: [
    qx.dev.unit.MRequirements,
    qx.dev.unit.MMock
  ],

  members:
    {
      setUp: function() {
        console.debug("Setting up .. ");
        this.debug("Setting up ...");
      },

      tearDown: function() {
        console.debug("Tear down .. ");
        this.debug("Tear down ...");
        this.getSandbox().restore();
      },

      /*
      ---------------------- -----------------------------------------------------
        TESTS
      ---------------------------------------------------------------------------
      */

      "test: login call to GET api/token": function() {
        console.debug("-----> testLogin", qxapp.auth);
        this.useFakeXMLHttpRequest();

        var manager = qxapp.auth.Manager.getInstance();

        var req = new qx.io.request.Xhr("api/auth", "GET");
        var fakeReq = this.getRequests()[0];

        manager.login("foo@itis.org", "secret", function(success, msg) {
          //
          this.assertEquals(success, false);
          this.assertEquals(msg, "Authentication Failed");
        }, this);


        this.assertEventFired(req, "statusError", function() {
          // The function which will be invoked and which fires the event.
          fakeReq.respond(200, {}, "true");
        });
      }

    }
});
