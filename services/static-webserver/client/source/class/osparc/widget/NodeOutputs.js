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
    */
  construct: function(node) {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox(15));

    const grid = new qx.ui.layout.Grid(5, 5);
    grid.setColumnFlex(this.self().POS.LABEL, 1);
    grid.setColumnFlex(this.self().POS.VALUE, 1);
    grid.setColumnMinWidth(this.self().POS.VALUE, 50);
    grid.setColumnMaxWidth(this.self().POS.RETRIEVE_STATUS, 25);
    Object.keys(this.self().POS).forEach((_, idx) => grid.setColumnAlign(idx, "left", "middle"));
    const gridLayout = this.__gridLayout = new qx.ui.container.Composite(grid);
    this._add(gridLayout);

    this.set({
      node,
      ports: node.getMetaData().outputs
    });

    node.addListener("changeOutputs", () => this.__outputsChanged(), this);

    this.addListener("appear", () => this.__makeLabelsResponsive(), this);
    this.addListener("resize", () => this.__makeLabelsResponsive(), this);
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
      PROBE: 5,
      RETRIEVE_STATUS: 6,
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

        const label = new qx.ui.basic.Label().set({
          rich: true,
          value: port.label,
          toolTipText: port.label
        });
        // leave ``rich`` set to true. Ellipsis will be handled here:
        label.getContentElement().setStyles({
          "text-overflow": "ellipsis",
          "white-space": "nowrap"
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

        this.__gridLayout.getLayout().setRowHeight(i, 23);
      }
    },

    __outputsChanged: function() {
      const outputs = this.getNode().getOutputs();
      const ports = this.getPorts();
      const portKeys = Object.keys(ports);
      for (let i=0; i<portKeys.length; i++) {
        const portKey = portKeys[i];
        const value = (portKey in outputs && "value" in outputs[portKey]) ? outputs[portKey]["value"] : null;
        if (value && typeof value === "object" && "store" in value && "eTag" in value) {
          // it's a file in storage.
          // check if the eTag changed before requesting the presigned link again
          const eTag = value["eTag"];
          const valueWidget = this.__getValueWidget(i);
          if (eTag && valueWidget && valueWidget.eTag && eTag === valueWidget.eTag) {
            continue;
          }
        }
        this.__valueToGrid(value, i);
      }
    },

    __getValueWidget: function(row) {
      const children = this.__gridLayout.getChildren();
      for (let i=0; i<children.length; i++) {
        const child = children[i];
        const layoutProps = child.getLayoutProperties();
        if (
          layoutProps.row === row &&
          layoutProps.column === this.self().POS.VALUE
        ) {
          return child;
        }
      }
      return null;
    },

    __valueToGrid: function(value, row) {
      let valueWidget = null;
      if (value && typeof value === "object") {
        valueWidget = new osparc.ui.basic.LinkLabel();
        if ("store" in value) {
          // it's a file
          const download = true;
          const locationId = value.store;
          const fileId = value.path;
          const filename = value.filename || osparc.file.FilePicker.getFilenameFromPath(value);
          valueWidget.setValue(filename);
          valueWidget.eTag = value["eTag"];
          osparc.store.Data.getInstance().getPresignedLink(download, locationId, fileId)
            .then(presignedLinkData => {
              if ("resp" in presignedLinkData && presignedLinkData.resp) {
                valueWidget.setUrl(presignedLinkData.resp.link);
              }
            });
        } else if ("downloadLink" in value) {
          // it's a link
          const filename = (value.filename && value.filename.length > 0) ? value.filename : osparc.file.FileDownloadLink.extractLabelFromLink(value["downloadLink"]);
          valueWidget.set({
            value: filename,
            url: value.downloadLink
          });
        }
      } else {
        valueWidget = new qx.ui.basic.Label("-");
        if (value) {
          valueWidget.setValue(String(value));
        }
      }

      // remove first if any
      this.__removeEntry(row, this.self().POS.VALUE);

      this.__gridLayout.add(valueWidget, {
        row: row,
        column: this.self().POS.VALUE
      });
    },

    __makeLabelsResponsive: function() {
      const grid = this.__gridLayout.getLayout();
      const firstColumnWidth = osparc.utils.Utils.getGridsFirstColumnWidth(grid);
      if (firstColumnWidth === null) {
        // not rendered yet
        setTimeout(() => this.__makeLabelsResponsive(), 100);
        return;
      }
      const extendedVersion = firstColumnWidth > 300;

      const ports = this.getPorts();
      const portKeys = Object.keys(ports);
      for (let i=0; i<portKeys.length; i++) {
        const portKey = portKeys[i];
        const port = ports[portKey];
        const label = grid.getCellWidget(i, this.self().POS.LABEL);
        const infoButton = grid.getCellWidget(i, this.self().POS.INFO);
        label.set({
          value: (extendedVersion ? port.label + port.description : port.label) + " :",
          toolTipText: extendedVersion ? port.label + "<br>" + port.description: port.label
        });
        infoButton.setVisibility(extendedVersion ? "hidden" : "visible");
        grid.setColumnMinWidth(this.self().POS.VALUE, extendedVersion ? 150 : 50);
      }
    },

    __removeEntry: function(row, column) {
      let children = this.__gridLayout.getChildren();
      for (let i=0; i<children.length; i++) {
        let child = children[i];
        const layoutProps = child.getLayoutProperties();
        if (
          layoutProps.row === row &&
          layoutProps.column === column
        ) {
          this.__gridLayout.remove(child);
          break;
        }
      }
    },

    setRetrievingStatus: function(portId, status) {
      const ports = this.getPorts();
      const portKeys = Object.keys(ports);
      const idx = portKeys.indexOf(portId);
      if (idx === -1) {
        return;
      }

      // remove first if any
      this.__removeEntry(idx, this.self().POS.RETRIEVE_STATUS);

      const icon = osparc.form.renderer.PropForm.getIconForStatus(status);
      this.__gridLayout.add(icon, {
        row: idx,
        column: this.self().POS.RETRIEVE_STATUS
      });
    }
  }
});
