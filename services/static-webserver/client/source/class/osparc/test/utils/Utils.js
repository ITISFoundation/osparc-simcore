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
    },

    testParseVersion: function() {
      // standard semver
      const v1 = osparc.utils.Utils.parseVersion("9.4.1");
      this.assertEquals(v1.major, 9);
      this.assertEquals(v1.minor, 4);
      this.assertEquals(v1.patch, 1);
      this.assertNull(v1.preRelease);

      // with pre-release
      const v2 = osparc.utils.Utils.parseVersion("9.4.0-rc.5");
      this.assertEquals(v2.major, 9);
      this.assertEquals(v2.minor, 4);
      this.assertEquals(v2.patch, 0);
      this.assertEquals(v2.preRelease, "rc.5");

      // missing patch
      const v3 = osparc.utils.Utils.parseVersion("1.2");
      this.assertEquals(v3.major, 1);
      this.assertEquals(v3.minor, 2);
      this.assertEquals(v3.patch, 0);

      // invalid inputs return null
      this.assertNull(osparc.utils.Utils.parseVersion(null));
      this.assertNull(osparc.utils.Utils.parseVersion(""));
      this.assertNull(osparc.utils.Utils.parseVersion("null"));
      this.assertNull(osparc.utils.Utils.parseVersion("v9.4.0"));
      this.assertNull(osparc.utils.Utils.parseVersion("abc"));
    },

    testHasMinorOrMajorBump: function() {
      // major bump
      this.assertTrue(osparc.utils.Utils.hasMinorOrMajorBump("1.0.0", "2.0.0"));
      // minor bump
      this.assertTrue(osparc.utils.Utils.hasMinorOrMajorBump("1.0.0", "1.1.0"));
      // patch only — no bump
      this.assertFalse(osparc.utils.Utils.hasMinorOrMajorBump("1.0.0", "1.0.1"));
      // same version
      this.assertFalse(osparc.utils.Utils.hasMinorOrMajorBump("1.0.0", "1.0.0"));
      // pre-release on same minor — no bump
      this.assertFalse(osparc.utils.Utils.hasMinorOrMajorBump("9.4.0", "9.4.0-rc.5"));
      // invalid input — returns false, not a crash
      this.assertFalse(osparc.utils.Utils.hasMinorOrMajorBump("null", "1.0.0"));
      this.assertFalse(osparc.utils.Utils.hasMinorOrMajorBump("1.0.0", null));
    },

    testCompareVersionNumbersPreRelease: function() {
      // pre-release suffix is stripped, so same major.minor.patch compares as equal
      this.assertEquals(osparc.utils.Utils.compareVersionNumbers("9.4.0-rc.5", "9.4.0"), 0);
      this.assertEquals(osparc.utils.Utils.compareVersionNumbers("9.4.0-rc.3", "9.4.0-rc.5"), 0);
      // patch difference still detected
      this.assertPositiveNumber(osparc.utils.Utils.compareVersionNumbers("9.4.1-rc.1", "9.4.0"));
      // invalid input returns 0
      this.assertEquals(osparc.utils.Utils.compareVersionNumbers("bad", "1.0.0"), 0);
    }
  }
});
