/* ************************************************************************

   osparc - the simcore frontend

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
qx.Class.define("osparc.test.data.MimeType",
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
        [
          ["image", null],
          ["data:*/*", "*/*"],
          ["data:text/csv", "text/csv"],
          ["data:image/svg+xml", "image/svg+xml"]
        ].forEach(pair => {
          const a = osparc.data.MimeType.getMimeType(pair[0]);
          this.assertIdentical(a, pair[1], "should return " + pair[1]);
        }, this);
      },

      testMatch: function() {
        const aPortType = "data:*/*";
        const bPortType = "data:text/csv";
        const aMimeType = osparc.data.MimeType.getMimeType(aPortType);
        const bMimeType = osparc.data.MimeType.getMimeType(bPortType);
        const a = new osparc.data.MimeType(aMimeType);
        const b = new osparc.data.MimeType(bMimeType);
        this.assert(a.match(b), "*/* should match everything");
      }
    }
  });
