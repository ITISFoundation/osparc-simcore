/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2021 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.node.ProbeView", {
  extend: qx.ui.core.Widget,

  construct: function(probe) {
    this.base();

    this._setLayout(new qx.ui.layout.VBox(16));

    if (probe) {
      this.setNode(probe);
    }
  },

  statics: {
    setProbeOutputValue: function(node, linkLabel) {
      const populateLinkLabel = linkInfo => {
        const locationId = linkInfo.store;
        const fileId = linkInfo.path;
        osparc.store.Data.getInstance().getPresignedLink(true, locationId, fileId)
          .then(presignedLinkData => {
            if ("resp" in presignedLinkData && presignedLinkData.resp) {
              const filename = linkInfo.filename || osparc.file.FilePicker.getFilenameFromPath(linkInfo);
              linkLabel.set({
                value: filename,
                url: presignedLinkData.resp.link
              });
            }
          });
      }

      const link = node.getLink("in_1");
      if (link && "nodeUuid" in link) {
        const inputNodeId = link["nodeUuid"];
        const portKey = link["output"];
        const inputNode = node.getWorkbench().getNode(inputNodeId);
        if (inputNode) {
          inputNode.bind("outputs", linkLabel, "value", {
            converter: outputs => {
              const output = outputs.find(out => out.getPortKey() === portKey);
              if (output && output.getValue() !== undefined) {
                const val = output.getValue();
                if (node.getMetadata()["key"].includes("probe/array") && Array.isArray(val)) {
                  return "[" + val.join(",") + "]";
                } else if (node.getMetadata()["key"].includes("probe/file")) {
                  const filename = val.filename || osparc.file.FilePicker.getFilenameFromPath(val);
                  populateLinkLabel(val);
                  return filename;
                }
                return String(val);
              }
              return "";
            }
          });
        } else {
          linkLabel.setValue("");
        }
      } else {
        linkLabel.setValue("");
      }
    },

    createProbeValueLabel: function(node) {
      const linkLabel = new osparc.ui.basic.LinkLabel().set({
        rich: false, // this will make the ellipsis work
      });

      node.getPropsForm().addListener("linkFieldModified", () => this.setProbeOutputValue(node, linkLabel));
      this.setProbeOutputValue(node, linkLabel);

      return linkLabel;
    },
  },

  properties: {
    node: {
      check: "osparc.data.model.Node",
      init: null,
      nullable: false,
      apply: "__applyNode"
    },
  },

  members: {
    __applyNode: function(node) {
      if (!node.isProbe()) {
        console.error("Only Probe nodes are supported");
      }
      this.__populateLayout(node);
    },

    __populateLayout: function(node) {
      this._removeAll();

      const inputs = new osparc.desktop.PanelView(this.tr("Input"), node.getPropsForm());
      this._add(inputs);

      const valueContainer = new qx.ui.container.Composite(new qx.ui.layout.HBox(16)).set({
        paddingTop: 8,
      });
      const icon = new qx.ui.basic.Image("@FontAwesome5Solid/thermometer/14");
      const valueLabel = osparc.node.ProbeView.createProbeValueLabel(node);
      valueContainer.add(icon);
      valueContainer.add(valueLabel, {
        flex: 1
      });
      const outputPanel = new osparc.desktop.PanelView(this.tr("Value"), valueContainer);
      this._add(outputPanel);
      // Hide the value panel when the probe is not connected
      valueLabel.addListener("changeVisibility", e => {
        outputPanel.setVisibility(e.getData());
      });
      outputPanel.setVisibility(valueLabel.getVisibility());
    },
  }
});
