/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2022 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/**
 * Here is a little example of how to use the widget.
 *
 * <pre class='javascript'>
 *   let nodeOutputs = new osparc.widget.NodeOutputs(node, port);
 *   this.getRoot().add(nodeOutputs);
 * </pre>
 */

qx.Class.define("osparc.widget.NodeOutputs", {
  extend: qx.ui.core.Widget,

  /**
    * @param node {osparc.data.model.Node} Node owning the widget
    * @param ports {Object} Port owning the widget
    */
  construct: function(node, ports) {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox(15));

    const grid = new qx.ui.layout.Grid(5, 5);
    grid.setColumnFlex(this.self().POS.LABEL, 1);
    grid.setColumnFlex(this.self().POS.INFO, 0);
    grid.setColumnFlex(this.self().POS.ICON, 0);
    grid.setColumnFlex(this.self().POS.VALUE, 1);
    grid.setColumnFlex(this.self().POS.UNIT, 0);
    grid.setColumnFlex(this.self().POS.PROBE, 0);
    grid.setColumnMinWidth(this.self().POS.VALUE, 50);
    Object.keys(this.self().POS).forEach((_, idx) => grid.setColumnAlign(idx, "left", "middle"));
    const gridLayout = this.__gridLayout = new qx.ui.container.Composite(grid).set({
      allowGrowX: false
    });
    this._add(gridLayout);

    this.set({
      node,
      ports
    });

    node.addListener("changeOutputs", () => this.__populateGrid(), this);
  },

  properties: {
    node: {
      check: "osparc.data.model.Node",
      nullable: false
    },

    ports: {
      nullable: false,
      apply: "__populateGrid"
    },

    offerProbes: {
      check: "Boolean",
      init: false,
      event: "changeOfferProbes"
    }
  },

  events: {
    "probeRequested": "qx.event.type.Data"
  },

  statics: {
    POS: {
      LABEL: 0,
      INFO: 1,
      ICON: 2,
      VALUE: 3,
      UNIT: 4,
      PROBE: 5
    }
  },

  members: {
    __gridLayout: null,

    __populateGrid: function() {
      this.__gridLayout.removeAll();

      const ports = this.getPorts();
      const portKeys = Object.keys(ports);
      for (let i=0; i<portKeys.length; i++) {
        const portKey = portKeys[i];
        const port = ports[portKey];

        const label = new qx.ui.basic.Label(port.label + " :").set({
          toolTipText: port.label
        });
        this.__gridLayout.add(label, {
          row: i,
          column: this.self().POS.LABEL
        });

        const infoButton = new osparc.ui.hint.InfoHint(port.description);
        this.__gridLayout.add(infoButton, {
          row: i,
          column: this.self().POS.INFO
        });

        const icon = new qx.ui.basic.Image(osparc.data.Converters.fromTypeToIcon(port.type));
        this.__gridLayout.add(icon, {
          row: i,
          column: this.self().POS.ICON
        });

        const value = port.value || null;
        if (value && typeof value === "object") {
          const valueLink = new osparc.ui.basic.LinkLabel();
          this.__gridLayout.add(valueLink, {
            row: i,
            column: this.self().POS.VALUE
          });
          if ("store" in value) {
            // it's a file
            const download = true;
            const locationId = value.store;
            const fileId = value.path;
            const filename = value.filename || osparc.file.FilePicker.getFilenameFromPath(value);
            valueLink.setValue(filename);
            osparc.store.Data.getInstance().getPresignedLink(download, locationId, fileId)
              .then(presignedLinkData => {
                if ("resp" in presignedLinkData && presignedLinkData.resp) {
                  valueLink.setUrl(presignedLinkData.resp.link);
                }
              });
          } else if ("downloadLink" in value) {
            // it's a link
            const filename = (value.filename && value.filename.length > 0) ? value.filename : osparc.file.FileDownloadLink.extractLabelFromLink(value["downloadLink"]);
            valueLink.set({
              value: filename,
              url: value.downloadLink
            });
          }
        } else {
          const valueEntry = new qx.ui.basic.Label("-");
          if (value) {
            valueEntry.setValue(String(value));
          }
          this.__gridLayout.add(valueEntry, {
            row: i,
            column: this.self().POS.VALUE
          });
        }

        const unit = new qx.ui.basic.Label(port.unitShort || "");
        this.__gridLayout.add(unit, {
          row: i,
          column: this.self().POS.UNIT
        });

        const probeBtn = new qx.ui.form.Button().set({
          icon: osparc.service.Utils.TYPES["probe"].icon + "12",
          height: 23,
          focusable: false,
          toolTipText: this.tr("Connects a Probe to this output")
        });
        this.bind("offerProbes", probeBtn, "visibility", {
          converter: val => val ? "visible" : "excluded"
        });
        probeBtn.addListener("execute", () => this.getNode().fireDataEvent("probeRequested", {
          portId: portKey,
          nodeId: this.getNode().getNodeId()
        }));
        this.__gridLayout.add(probeBtn, {
          row: i,
          column: this.self().POS.PROBE
        });
      }
    }
  }
});
