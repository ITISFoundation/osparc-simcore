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
        const studyData = {
          name: "Test Study",
          description: ""
        };
        const prj = new qxapp.data.model.Study(studyData);
        const wbData = {};
        this.__workbench = new qxapp.data.model.Workbench(prj, wbData);
      },

      tearDown: function() {
        console.debug("Tear down .. ");
        this.debug("Tear down ...");
        this.getSandbox().restore();
      },

      createDummyNode() {
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

      testDuplicatedNodeConnections: function() {
        const linkId = null;
        const node1 = this.createDummyNode();
        const node2 = this.createDummyNode();
        const link1 = this.__workbench.createEdge(linkId, node1.getNodeId(), node2.getNodeId());
        const link2 = this.__workbench.createEdge(linkId, node1.getNodeId(), node2.getNodeId());
        this.assertIdentical(link1.getEdgeId(), link2.getEdgeId(), "Both links must be the same");
      },

      testUniqueName: function() {
        const node1 = this.createDummyNode();
        const node2 = this.createDummyNode();
        this.assertNotIdentical(node1.getLabel(), node2.getLabel(), "Labels must be different");
      }
    }
  });
