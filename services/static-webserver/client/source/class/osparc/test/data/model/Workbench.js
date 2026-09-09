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
 * Test Workbench class
 *
 */
qx.Class.define("osparc.test.data.model.Workbench",
  {
    extend: qx.dev.unit.TestCase,
    include: [qx.dev.unit.MRequirements, qx.dev.unit.MMock],

    members:
    {
      setUp: function() {
        console.debug("Setting up .. ");
        this.debug("Setting up ...");

        // TODO OM: Tobi is this correct?
        osparc.data.Permissions.getInstance().setRole("user");

        // Workbench.createNode requires a study context (uuid and pipeline state)
        const study = new osparc.data.model.Study({
          uuid: "test-study-id"
        });
        this.__workbench = study.getWorkbench();

        // createNode creates the node in the backend first and then fetches its
        // metadata. Mock both interactions to keep the test isolated from the network.
        this.stub(osparc.data.Resources, "fetch", () => Promise.resolve({
          "node_id": osparc.utils.Utils.uuidV4()
        }));
        this.stub(osparc.data.model.Node.prototype, "fetchMetadataAndPopulate", () => Promise.resolve());
      },

      tearDown: function() {
        console.debug("Tear down .. ");
        this.debug("Tear down ...");
        this.getSandbox().restore();
      },

      createDummyNode() {
        const key = null;
        const version = null;
        return this.__workbench.createNode(key, version);
      },

      /*
      ---------------------- -----------------------------------------------------
        TESTS
      ---------------------------------------------------------------------------
      */

      testDuplicatedNodeConnections: function() {
        const edgeId = null;
        Promise.all([this.createDummyNode(), this.createDummyNode()])
          .then(([node1, node2]) => this.resume(function() {
            const edge1 = this.__workbench.createEdge(edgeId, node1.getNodeId(), node2.getNodeId());
            const edge2 = this.__workbench.createEdge(edgeId, node1.getNodeId(), node2.getNodeId());
            this.assertIdentical(edge1.getEdgeId(), edge2.getEdgeId(), "Both edges must be the same");
          }, this));
        this.wait(5000);
      },

      testUniqueName: function() {
        Promise.all([this.createDummyNode(), this.createDummyNode()])
          .then(([node1, node2]) => this.resume(function() {
            this.assertNotIdentical(node1.getLabel(), node2.getLabel(), "Labels must be different");
          }, this));
        this.wait(5000);
      },

      testNodeAddedToBackendFiredOnce: function() {
        const eventSpy = this.spy();
        this.__workbench.addListener("nodeAddedToBackend", eventSpy, this);

        const key = "simcore/services/dynamic/test";
        const version = "1.0.0";
        this.__workbench.createNode(key, version)
          .then(node => this.resume(function() {
            this.assertNotNull(node, "A node should have been created");
            this.assertCalledOnce(eventSpy);
            this.assertIdentical(node, eventSpy.getCall(0).args[0].getData(), "The event must carry the created node");
          }, this));
        this.wait(5000);
      }
    }
  });
