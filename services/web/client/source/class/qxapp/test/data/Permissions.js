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
 * Test Permissions
 *
 */
qx.Class.define("qxapp.test.data.Permissions", {
  extend: qx.dev.unit.TestCase,
  include: [qx.dev.unit.MRequirements, qx.dev.unit.MMock],

  members: {
    __studyEditor: null,
    __workbench: null,

    setUp: function() {
      console.debug("Setting up .. ");
      this.debug("Setting up ...");
    },

    tearDown: function() {
      console.debug("Tear down .. ");
      this.debug("Tear down ...");
      this.getSandbox().restore();
    },

    createEmptyWorkbench: function() {
      const studyData = {
        name: "Test Study",
        description: ""
      };
      const study = this.__studyEditor = new qxapp.data.model.Study(studyData);
      const wbData = {};
      this.__workbench = new qxapp.data.model.Workbench(study, wbData);
    },

    createDummyNode: function() {
      const key = null;
      const version = null;
      const uuid = null;
      const parent = null;
      const populateNodeData = true;
      return this.__workbench.createNode(key, version, uuid, parent, populateNodeData);
    },

    /*
    ---------------------- -----------------------------------------------------
      TESTS
    ---------------------------------------------------------------------------
    */

    testStudyNodeCreate: function() {
      this.createEmptyWorkbench();

      qxapp.data.Permissions.getInstance().setRole("anonymous");
      const anonNode = this.createDummyNode();
      this.assertNull(anonNode, "anonymous is not allowed to create nodes");

      qxapp.data.Permissions.getInstance().setRole("user");
      const userNode = this.createDummyNode();
      this.assertNotNull(userNode, "user is allowed to create nodes");
    },

    testStudyNodeDelete: function() {
      this.createEmptyWorkbench();

      qxapp.data.Permissions.getInstance().setRole("user");
      const dummyNode = this.createDummyNode();
      this.assertNotNull(dummyNode, "user is allowed to create nodes");

      qxapp.data.Permissions.getInstance().setRole("anonymous");
      let removed = this.__workbench.removeNode(dummyNode.getNodeId()); // eslint-disable-line no-underscore-dangle
      this.assertFalse(removed, "anonymous is not allowed to delete nodes");

      qxapp.data.Permissions.getInstance().setRole("user");
      removed = this.__workbench.removeNode(dummyNode.getNodeId()); // eslint-disable-line no-underscore-dangle
      this.assertTrue(removed, "user is allowed to delete nodes");
    }
  }
});
