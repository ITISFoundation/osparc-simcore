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

    this._setLayout(new qx.ui.layout.VBox());

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
              if (output && output.getValue()) {
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
      const inputsForm = node.getPropsForm();
      const inputs = new osparc.desktop.PanelView(this.tr("Inputs"), inputsForm);
      inputs._innerContainer.set({
        margin: 8
      });
      this._add(inputs);
    },
  }
});
