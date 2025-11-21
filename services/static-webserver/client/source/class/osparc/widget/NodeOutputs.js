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
 *   let nodeOutputs = new osparc.widget.NodeOutputs(node);
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
    grid.setColumnMaxWidth(this.self().POS.PORT_STATUS_ICON, 25);
    Object.keys(this.self().POS).forEach((_, idx) => grid.setColumnAlign(idx, "left", "middle"));
    const gridLayout = this.__gridLayout = new qx.ui.container.Composite(grid);
    this._add(gridLayout);

    this.set({
      node,
    });

    node.addListener("changeOutputs", () => this.__outputsChanged(), this);

    this.addListener("appear", () => this.__makeLabelsResponsive(), this);
    this.addListener("resize", () => this.__makeLabelsResponsive(), this);
  },

  properties: {
    node: {
      check: "osparc.data.model.Node",
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
      PORT_STATUS_ICON: 6,
    }
  },

  members: {
    __gridLayout: null,

    __populateGrid: function(node) {
      this.__gridLayout.removeAll();

      node.getOutputs().forEach((output, i) => {
        const label = new qx.ui.basic.Label().set({
          rich: true,
          value: output.getLabel(),
          toolTipText: output.getLabel()
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

        const infoButton = new osparc.ui.hint.InfoHint(output.getDescription());
        this.__gridLayout.add(infoButton, {
          row: i,
          column: this.self().POS.INFO
        });

        const icon = new qx.ui.basic.Image(osparc.data.Converters.fromTypeToIcon(output.getType()));
        this.__gridLayout.add(icon, {
          row: i,
          column: this.self().POS.ICON
        });

        const unit = new qx.ui.basic.Label(output["unitShort"] || "");
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
        const portKey = output.getPortKey();
        osparc.utils.Utils.setIdToWidget(probeBtn, "connect_probe_btn_" + portKey);
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

        const statusIcon = new qx.ui.basic.Atom().set({
          visibility: "excluded"
        });
        this.__gridLayout.add(statusIcon, {
          row: i,
          column: this.self().POS.PORT_STATUS_ICON
        });
        output.bind("status", statusIcon, "visibility", {
          converter: status => status ? "visible" : "excluded"
        });
        output.bind("status", statusIcon, "icon", {
          converter: status => {
            let retrievingStatus = null;
            switch (status) {
              case "UPLOAD_STARTED":
                retrievingStatus = osparc.form.renderer.PropForm.RETRIEVE_STATUS.uploading;
                break;
              case "UPLOAD_FINISHED_SUCCESSFULLY":
                retrievingStatus = osparc.form.renderer.PropForm.RETRIEVE_STATUS.succeed;
                break;
              case "UPLOAD_WAS_ABORTED":
              case "UPLOAD_FINISHED_WITH_ERROR":
                retrievingStatus = osparc.form.renderer.PropForm.RETRIEVE_STATUS.failed;
                break;
            }
            if (retrievingStatus !== null) {
              return osparc.form.renderer.PropForm.getPortStatusIcon(retrievingStatus);
            }
            return null;
          }
        });

        this.__gridLayout.getLayout().setRowHeight(i, 23);
      });
    },

    __outputsChanged: function() {
      const outputs = this.getNode().getOutputs();
      outputs.forEach((output, idx) => {
        const value = output.getValue();
        if (value && typeof value === "object" && "store" in value && "eTag" in value) {
          // it's a file in storage.
          // check if the eTag changed before requesting the presigned link again
          const eTag = value["eTag"];
          const valueWidget = this.__getValueWidget(idx);
          if (eTag && valueWidget && valueWidget.eTag && eTag === valueWidget.eTag) {
            return;
          }
        }
        this.__valueToGrid(value, idx);
      });
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
          const filename = value.filename || osparc.file.FilePicker.getFilenameFromPath(value);
          valueWidget.setValue(filename);
          valueWidget.eTag = value["eTag"];
          const download = true;
          const locationId = value.store;
          const fileId = value.path;
          // request the presigned link only when the widget is shown
          valueWidget.addListenerOnce("appear", () => {
            osparc.store.Data.getInstance().getPresignedLink(download, locationId, fileId)
              .then(presignedLinkData => {
                if ("resp" in presignedLinkData && presignedLinkData.resp) {
                  valueWidget.setUrl(presignedLinkData.resp.link);
                }
              });
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

      const outputs = this.getNode().getOutputs();
      outputs.forEach((output, i) => {
        const label = grid.getCellWidget(i, this.self().POS.LABEL);
        const infoButton = grid.getCellWidget(i, this.self().POS.INFO);
        const title = output.getLabel();
        const description = output.getDescription();
        label.set({
          value: (extendedVersion ? title + description : title) + " :",
          toolTipText: extendedVersion ? title + "<br>" + description: title
        });
        infoButton.setVisibility(extendedVersion ? "hidden" : "visible");
        grid.setColumnMinWidth(this.self().POS.VALUE, extendedVersion ? 150 : 50);
      });
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
  }
});
