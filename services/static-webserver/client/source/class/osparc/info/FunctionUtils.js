/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2025 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */


qx.Class.define("osparc.info.FunctionUtils", {
  type: "static",

  statics: {
    /**
      * @param func {osparc.data.model.Function} Function Model
      */
    createTitle: function(func) {
      const title = osparc.info.Utils.createTitle();
      func.bind("title", title, "value");
      return title;
    },

    /**
      * @param func {osparc.data.model.Function} Function Model
      * @param maxHeight {Number} description's maxHeight
      */
    createDescription: function(func, maxHeight) {
      const description = new osparc.ui.markdown.Markdown();
      func.bind("description", description, "value", {
        converter: desc => desc ? desc : "No description"
      });
      const scrollContainer = new qx.ui.container.Scroll();
      if (maxHeight) {
        scrollContainer.setMaxHeight(maxHeight);
      }
      scrollContainer.add(description);
      return scrollContainer;
    },

    /**
      * @param func {osparc.data.model.Function} Function Model
      */
    createOwner: function(func) {
      const owner = new qx.ui.basic.Label();
      const canIWrite = func.canIWrite();
      owner.setValue(canIWrite ? "My Function" : "Read Only");
      return owner;
    },

    /**
      * @param func {osparc.data.model.Function} Function Model
      */
    createCreationDate: function(func) {
      const creationDate = new qx.ui.basic.Label();
      func.bind("creationDate", creationDate, "value", {
        converter: date => osparc.utils.Utils.formatDateAndTime(date)
      });
      return creationDate;
    },

    /**
      * @param func {osparc.data.model.Function} Function Model
      */
    createLastChangeDate: function(func) {
      const lastChangeDate = new qx.ui.basic.Label();
      func.bind("lastChangeDate", lastChangeDate, "value", {
        converter: date => osparc.utils.Utils.formatDateAndTime(date)
      });
      return lastChangeDate;
    },

    /**
      * @param func {osparc.data.model.Function} Function Model
      * @param maxWidth {Number} thumbnail's maxWidth
      * @param maxHeight {Number} thumbnail's maxHeight
      */
    createThumbnail: function(func, maxWidth, maxHeight) {
      const thumbnail = osparc.info.Utils.createThumbnail(maxWidth, maxHeight);
      const noThumbnail = "osparc/no_photography_black_24dp.svg";
      func.bind("thumbnail", thumbnail, "source", {
        converter: thumb => thumb ? thumb : noThumbnail,
        onUpdate: (source, target) => {
          if (source.getThumbnail() === "") {
            target.getChildControl("image").set({
              minWidth: 120,
              minHeight: 139
            });
          }
        }
      });
      return thumbnail;
    },
  }
});
