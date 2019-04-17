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
 * Test Workbench class
 *
 */
qx.Class.define("qxapp.test.data.model.Workbench",
  {
    extend: qx.dev.unit.TestCase,
    include: [qx.dev.unit.MRequirements, qx.dev.unit.MMock],

    members:
    {
      setUp: function() {
        console.debug("Setting up .. ");
        this.debug("Setting up ...");
        const prjName = "testStudy";
        const wbData = {};
        this.__workbench = new qxapp.data.model.Workbench(prjName, wbData);
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

      testUniqueName: function() {
        const key = null;
        const version = null;
        const uuid = null;
        const parent = null;
        const populateNodeData = false;
        const node1 = this.__workbench.createNode(key, version, uuid, parent, populateNodeData);
        const node2 = this.__workbench.createNode(key, version, uuid, parent, populateNodeData);
        this.assertNotIdentical(node1.getLabel(), node2.getLabel(), "Labels must be different");
      }
    }
  });
