/*
 * oSPARC - The SIMCORE frontend - https://osparc.io
 * Copyright: 2019 IT'IS Foundation - https://itis.swiss
 * License: MIT - https://opensource.org/licenses/MIT
 * Authors: Ignacio Pascual (ignapas)
 *          Odei Maiz (odeimaiz)
 */

/**
 * Widget that contains the StudyDetails of the given study metadata.
 *
 * It also provides a button that opens a window with the same information.
 *
 * *Example*
 *
 * Here is a little example of how to use the widget.
 *
 * <pre class='javascript'>
 *    const serviceInfo = new osparc.component.metadata.ServiceInfo(selectedService);
 *    this.add(serviceInfo);
 * </pre>
 */

qx.Class.define("osparc.component.export.ExportMacro", {
  extend: qx.ui.core.Widget,

  /**
    * @param node {osparc.data.model.Node} Node owning the widget
    */
  construct: function(node) {
    this.base(arguments, new qx.ui.layout.VBox(5));

    const key = "simcore/macros/" + osparc.utils.Utils.uuidv4();
    const version = "1.0.0";

    this.set({
      inputNode: node,
      outputNode: new osparc.data.model.Node(key, version)
    });

    this.__buildLayout();
  },

  properties: {
    inputNode: {
      check: "osparc.data.model.Node",
      nullable: false
    },

    outputNode: {
      check: "osparc.data.model.Node",
      nullable: false
    }
  },

  members: {
    __buildLayout: function() {
      const formRenderer = this.__buildMetaDataForm();
      this.__buildInputSettings();
      this.__buildExposedSettings();

      this._add(formRenderer);
      const settingsLayout = new qx.ui.container.Composite(new qx.ui.layout.HBox(10));
      this._add(settingsLayout);
    },

    __buildMetaDataForm: function() {
      const metaDataForm = new qx.ui.form.Form();

      const serviceName = new qx.ui.form.TextField();
      serviceName.setRequired(true);
      metaDataForm.add(serviceName, this.tr("Name"));

      const serviceDesc = new qx.ui.form.TextField();
      metaDataForm.add(serviceDesc, this.tr("Description"));

      const formRenderer = new qx.ui.form.renderer.Single(metaDataForm).set({
        padding: 10
      });
      return formRenderer;
    },

    __buildInputSettings: function() {
      console.log(this.getInputNode());
    },

    __buildExposedSettings: function() {
    }
  }
});
