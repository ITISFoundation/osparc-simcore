/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2023 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.component.resourceUsage.Overview", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox(15));

    const loadingImage = this.getChildControl("loading-image");
    loadingImage.show();
    const table = this.getChildControl("usage-table");
    table.exclude();

    this.__fetchData();
  },

  statics: {
    ITEMS_PER_PAGE: 15,

    popUpInWindow: function() {
      const title = qx.locale.Manager.tr("Usage Overview");
      const noteEditor = new osparc.component.resourceUsage.Overview();
      const viewWidth = 900;
      const viewHeight = 450;
      const win = osparc.ui.window.Window.popUpInWindow(noteEditor, title, viewWidth, viewHeight);
      win.center();
      win.open();
      return win;
    }
  },

  members: {
    __nextRequestParams: null,

    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "loading-image":
          control = new qx.ui.basic.Image().set({
            source: "@FontAwesome5Solid/paw/14",
            alignX: "center",
            alignY: "middle",
            height: (this.self().ITEMS_PER_PAGE*20 + 40)
          });
          this._add(control);
          break;
        case "usage-table":
          control = new osparc.component.resourceUsage.OverviewTable().set({
            height: (this.self().ITEMS_PER_PAGE*20 + 40)
          });
          this._add(control);
          break;
        case "page-buttons":
          control = new qx.ui.container.Composite(new qx.ui.layout.HBox(5)).set({
            alignX: "center",
            alignY: "middle"
          });
          this._add(control);
          break;
        case "prev-page-button": {
          control = new qx.ui.form.Button(this.tr("Prev")).set({
            allowGrowX: false
          });
          const pageButtons = this.getChildControl("page-buttons");
          pageButtons.add(control);
          break;
        }
        case "current-page-label": {
          control = new qx.ui.basic.Label().set({
            font: "text-14",
            textAlign: "center"
          });
          const pageButtons = this.getChildControl("page-buttons");
          pageButtons.add(control);
          break;
        }
        case "next-page-button": {
          control = new qx.ui.form.Button(this.tr("Next")).set({
            allowGrowX: false
          });
          const pageButtons = this.getChildControl("page-buttons");
          pageButtons.add(control);
          break;
        }
      }
      return control || this.base(arguments, id);
    },

    __fetchData: function() {
      const loadingImage = this.getChildControl("loading-image");
      loadingImage.show();
      const table = this.getChildControl("usage-table");
      table.exclude();

      this.__getNextRequest()
        .then(resp => {
          const data = resp["data"];
          this.__nextRequestParams = resp["_links"]["next"];
          this.__setData(data);
          this.__enableButtons();
        })
        .finally(() => {
          loadingImage.exclude();
          table.show();
        });
    },

    __getNextRequest: function() {
      const params = {
        url: {
          offset: 0,
          limit: osparc.component.resourceUsage.Overview.ITEMS_PER_PAGE
        }
      };
      const nextRequestParams = this.__nextRequestParams;
      if (nextRequestParams) {
        params.url.offset = nextRequestParams.offset;
        params.url.limit = nextRequestParams.limit;
      }
      const options = {
        resolveWResponse: true
      };
      return osparc.data.Resources.fetch("resourceUsage", "getPage", params, undefined, options);
    },

    __setData: function(data) {
      const table = this.getChildControl("usage-table");
      table.addData(data);
    },

    __enableButtons:function() {
      this.getChildControl("prev-page-button").setEnabled(false);
      this.getChildControl("current-page-label").setValue("1");
      this.getChildControl("next-page-button").setEnabled(false);
    }
  }
});
