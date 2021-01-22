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

qx.Mixin.define("osparc.ui.tree.MHintInTree", {
  properties: {
    description: {
      check: "String",
      init: null,
      event: "changeDescription",
      apply: "__recreateInfoButton",
      nullable: true
    },

    url: {
      check: "String",
      init: null,
      event: "changeUrl",
      apply: "__recreateInfoButton",
      nullable: true
    }
  },

  statics: {
    bindHintProps: function(controller, item, id) {
      controller.bindProperty("description", "description", null, item, id);
      controller.bindProperty("url", "url", null, item, id);
    }
  },

  members: {
    __recreateInfoButton: function() {
      if (this.__infoButton) {
        const idx = this._indexOf(this.__infoButton);
        if (idx !== -1) {
          this._remove(this.__infoButton);
        }
      }

      const desc = this.getDescription();
      const url = this.getUrl();
      const hints = [];
      if (desc !== "" && desc !== null) {
        hints.push(desc);
      }
      if (url !== "" && url !== null) {
        const link = "<a href=" + url + " target='_blank'>More...</a>";
        const linkWithRightColor = link.replace(/^<a /, "<a style=\"color:"+ qx.theme.manager.Color.getInstance().getTheme().colors["link"] + "\"");
        hints.push(linkWithRightColor);

        const themeManager = qx.theme.manager.Meta.getInstance();
        themeManager.addListener("changeTheme", () => {
          this.__recreateInfoButton();
        }, this);
      }
      if (hints.length) {
        const hint = hints.join("<br>");
        this.__infoButton = new osparc.component.form.FieldWHint("", hint, new qx.ui.basic.Label("")).set({
          maxWidth: 150
        });
        this._add(this.__infoButton);
      }
    }
  }
});
