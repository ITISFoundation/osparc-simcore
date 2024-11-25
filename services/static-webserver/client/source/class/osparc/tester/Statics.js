/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2024 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.tester.Statics", {
  extend: osparc.po.BaseView,

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "statics-container":
          control = osparc.ui.window.TabbedView.createSectionBox(this.tr("Statics"));
          this._add(control, {
            flex: 1
          });
          break;
        case "statics-content": {
          const statics = osparc.store.Store.getInstance().get("statics");
          const form = new qx.ui.form.Form();
          for (let [key, value] of Object.entries(statics)) {
            const textField = new qx.ui.form.TextField().set({
              value: typeof value === "object" ? JSON.stringify(value) : value.toString(),
              readOnly: true
            });
            form.add(textField, key, null, key);
          }
          const renderer = new qx.ui.form.renderer.Single(form);
          control = new qx.ui.container.Scroll(renderer);
          this.getChildControl("statics-container").add(control);
          break;
        }
        case "local-storage-container":
          control = osparc.ui.window.TabbedView.createSectionBox(this.tr("Local Storage"));
          this._add(control);
          break;
        case "local-storage-content": {
          const items = {
            ...window.localStorage
          };
          const form = new qx.ui.form.Form();
          for (let [key, value] of Object.entries(items)) {
            const textField = new qx.ui.form.TextField().set({
              value: typeof value === "object" ? JSON.stringify(value) : value.toString(),
              readOnly: true
            });
            form.add(textField, key, null, key);
          }
          control = new qx.ui.form.renderer.Single(form);
          this.getChildControl("local-storage-container").add(control);
          break;
        }
      }
      return control || this.base(arguments, id);
    },

    _buildLayout: function() {
      this.getChildControl("statics-content");
      this.getChildControl("local-storage-content");
    },
  }
});
