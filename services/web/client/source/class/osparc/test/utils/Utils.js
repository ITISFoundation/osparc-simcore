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
 * Test Utils
 *
 */
qx.Class.define("osparc.test.utils.Utils", {
  extend: qx.dev.unit.TestCase,
  include: [qx.dev.unit.MRequirements, qx.dev.unit.MMock],

  members: {
    __workbench: null,

    setUp: function() {
      console.debug("Setting up .. ");
      this.debug("Setting up ...");
    },

    tearDown: function() {
      console.debug("Tear down .. ");
      this.debug("Tear down ...");
    },

    /*
    ---------------------- -----------------------------------------------------
      TESTS
    ---------------------------------------------------------------------------
    */

    testCompareVersionNumbers: function() {
      this.assertPositiveNumber(osparc.utils.Utils.compareVersionNumbers("1.0.1", "1.0.0"));
      this.assertPositiveNumber(-1*osparc.utils.Utils.compareVersionNumbers("1.0.0", "1.0.1"));
      this.assertEquals(osparc.utils.Utils.compareVersionNumbers("1.0.1", "1.0.1"), 0);

      const unsorted = [
        "1.0.5",
        "1.0.4",
        "2.8.0",
        "2.11.0",
        "2.10.0",
        "2.9.0"
      ];
      const sorted = [
        "1.0.4",
        "1.0.5",
        "2.8.0",
        "2.9.0",
        "2.10.0",
        "2.11.0"
      ];
      const result = unsorted.sort(osparc.utils.Utils.compareVersionNumbers);
      this.assertArrayEquals(sorted, result);
    }
  }
});
