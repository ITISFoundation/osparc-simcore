/* ************************************************************************

   qxapp - the simcore frontend

   https://osparc.io

   Copyright:
     2019 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/**
 * Test MimeType class
 *
 */
qx.Class.define("qxapp.test.data.MimeType",
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
        TESTS
      ---------------------------------------------------------------------------
      */

      testGetMimeType: function() {
        const aPortType = "image";
        const a = qxapp.data.MimeType.getMimeType(aPortType);
        this.assertIdentical(a, null, "should return null");

        const bPortType = "data:*/*";
        const b = qxapp.data.MimeType.getMimeType(bPortType);
        this.assertIdentical(b, "*/*", "should return */*");

        const cPortType = "data:text/csv";
        const c = qxapp.data.MimeType.getMimeType(cPortType);
        this.assertIdentical(c, "data:text/csv", "should return text/csv");
      },

      testMatch: function() {
        const aPortType = "data:*/*";
        const bPortType = "data:text/csv";
        const a = qxapp.data.MimeType.getMimeType(aPortType);
        const b = qxapp.data.MimeType.getMimeType(bPortType);
        this.assert(a.match(b), "*/* should match everything");
      }
    }
  });
