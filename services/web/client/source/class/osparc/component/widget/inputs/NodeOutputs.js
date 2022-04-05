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
 *   let nodeOutputs = new osparc.component.widget.inputs.NodeOutputs(node, port);
 *   this.getRoot().add(nodeOutputs);
 * </pre>
 */

qx.Class.define("osparc.component.widget.inputs.NodeOutputs", {
  extend: qx.ui.core.Widget,

  /**
    * @param node {osparc.data.model.Node} Node owning the widget
    * @param ports {Object} Port owning the widget
    */
  construct: function(node, ports) {
    this.base(arguments);

    const layout = new qx.ui.layout.Grid(5, 5);
    layout.setColumnFlex(1, 1);
    layout.setColumnMaxWidth(1, 130);
    this._setLayout(layout);

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
    }
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
      }
    }
  },

  members: {
    __populateLayout: function() {
      const ports = Object.values(this.getPorts());
      for (let i=0; i<ports.length; i++) {
        const port = ports[i];

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
                if ("presignedLink" in presignedLinkData && presignedLinkData.presignedLink) {
                  valueLink.setUrl(presignedLinkData.presignedLink.link);
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
      }
    }
  }
});
