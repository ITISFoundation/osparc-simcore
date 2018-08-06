
/**
 * To setup test
 *
 *
 *
 */
qx.Class.define("qxapp.test.DemoTest",
  {
    extend: qx.dev.unit.TestCase,
    include: [qx.dev.unit.MRequirements, qx.dev.unit.MMock],

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
        TESTS  qx.dev.unit.TestCase assert functions
      ---------------------------------------------------------------------------
      */

      testAdvanced: function() {
        var a = 3;
        var b = a;
        this.assertIdentical(a, b, "A rose by any other name is still a rose");
        this.assertInRange(3, 1, 10, "You must be kidding, 3 can never be outside [1,10]!");
      },

      testFail: function() {
        var ab = 3;
        this.assertEquals(3, ab);
      },

      /*
      ---------------------- -----------------------------------------------------
        TESTS  with fakes. See qx.dev.unit.MMock
      ---------------------------------------------------------------------------
      */

      "test: spy this function": function() {
        var obj = {
          mymethod: function() { }
        };
        this.spy(obj, "mymethod");

        // run function to be tested
        // foo(spy);
        // spy();
        obj.mymethod();

        this.assertCalled(obj.mymethod);
      },


      /*
      ---------------------- -----------------------------------------------------
        TESTS  with requirements. See qqx.dev.unit.MRequirements
      ---------------------------------------------------------------------------
      */

      testWithRequirements: function() {
        this.require(["qx.debug"]);
        // test code goes here
        this.debug("This is running in debug");
        qx.log.Logger.debug("This is running");
      },

      testWithUI: function() {
        console.debug("Requirement helpers:", this.hasChrome(), this.hasGuiApp());

        this.require(["chrome", "guiApp"]);
        this.debug("this is running");
      },

      /*
      ---------------------- -----------------------------------------------------
        TESTS async
      ---------------------------------------------------------------------------
      */
      "test: GET api/auth async": function() {
        this.useFakeXMLHttpRequest();

        var req = new qx.io.request.Xhr("api/auth", "GET");
        var fakeReq = this.getRequests()[0];

        req.addListener("success", function(e) {
          this.resume(function() {
            // checks after async------------------------
            this.assertEquals(200, req.status);

            var body = (req.getBody()=="true");
            this.assertEquals(body, true);

            this.assertCalled(req.onreadystatechange);
            this.assertEquals("Response", req.responseText);
            //-------------------------------------------
          }, this);
        }, this);

        this.assertEventFired(req, "statusError", function() {
          // The function which will be invoked and which fires the event.
          fakeReq.respond(200, {}, "true");
        });
        req.send();

        this.assertEquals(fakeReq, req.getTransport().getRequest());
        this.wait(10000);
      }
    }
  });
