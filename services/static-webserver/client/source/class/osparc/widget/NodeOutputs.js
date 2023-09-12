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

    const grid = new qx.ui.layout.Grid(5, 5);
    grid.setColumnMaxWidth(this.self().POS.NAME, 140);
    grid.setColumnFlex(this.self().POS.VALUE, 1);
    Object.keys(this.self().POS).forEach((_, idx) => {
      grid.setColumnAlign(idx, "left", "middle");
    });
    this._setLayout(grid);

    this.set({
      node,
      ports
    });

    node.addListener("changeOutputs", () => this.__populateLayout(), this);
  },

  properties: {
    node: {
      check: "osparc.data.model.Node",
      nullable: false
    },

    ports: {
      nullable: false,
      apply: "__populateLayout"
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
      KEY: {
        col: 0
      },
      NAME: {
        col: 1
      },
      INFO: {
        col: 2
      },
      ICON: {
        col: 3
      },
      VALUE: {
        col: 4
      },
      UNIT: {
        col: 5
      },
      PROBE: {
        col: 6
      }
    }
  },

  members: {
    __populateLayout: function() {
      this._removeAll();

      const ports = this.getPorts();
      const portKeys = Object.keys(ports);
      for (let i=0; i<portKeys.length; i++) {
        const portKey = portKeys[i];
        const port = ports[portKey];

        const name = new qx.ui.basic.Label(port.label).set({
          toolTipText: port.label
        });
        this._add(name, {
          row: i,
          column: this.self().POS.NAME.col
        });

        const infoButton = new osparc.ui.hint.InfoHint(port.description);
        this._add(infoButton, {
          row: i,
          column: this.self().POS.INFO.col
        });

        const icon = new qx.ui.basic.Image(osparc.data.Converters.fromTypeToIcon(port.type));
        this._add(icon, {
          row: i,
          column: this.self().POS.ICON.col
        });

        const value = port.value || null;
        if (value && typeof value === "object") {
          const valueLink = new osparc.ui.basic.LinkLabel();
          this._add(valueLink, {
            row: i,
            column: this.self().POS.VALUE.col
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
          this._add(valueEntry, {
            row: i,
            column: this.self().POS.VALUE.col
          });
        }

        const unit = new qx.ui.basic.Label(port.unitShort || "");
        this._add(unit, {
          row: i,
          column: this.self().POS.UNIT.col
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
        this._add(probeBtn, {
          row: i,
          column: this.self().POS.PROBE.col
        });
      }
    }
  }
});
