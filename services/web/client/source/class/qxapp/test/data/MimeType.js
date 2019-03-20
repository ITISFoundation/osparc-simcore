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

/* eslint no-underscore-dangle: 0 */

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

      testMatch: function() {
        const store = qxapp.data.Store.getInstance();
        const aPortType = "data:*/*";
        const bPortType = "data:text/csv";
        const a = store.__getMatchType(aPortType);
        const b = store.__getMatchType(bPortType);
        this.assert(a.match(b), "*/* should match everything");
      }
    }
  });
