/*
 * oSPARC - The SIMCORE frontend - https://osparc.io
 * Copyright: 2019 IT'IS Foundation - https://itis.swiss
 * License: MIT - https://opensource.org/licenses/MIT
 * Authors: Ignacio Pascual (ignapas)
 *          Odei Maiz (odeimaiz)
 */

/**
 * Widget that displays the available information of the given study metadata.
 *
 * *Example*
 *
 * Here is a little example of how to use the widget.
 *
 * <pre class='javascript'>
 *    const studyDetails = new osparc.component.metadata.StudyDetails(study);
 *    this.add(studyDetails);
 * </pre>
 */

qx.Class.define("osparc.component.metadata.StudyDetails", {
  extend: qx.ui.core.Widget,

  /**
    * @param studyData {Object|osparc.data.model.Study} studyData (metadata)
    * @param maxHeight {Integer} Max Height of the thumbnail
    */
  construct: function(studyData, maxHeight) {
    this.base(arguments);
    this._setLayout(new qx.ui.layout.VBox(10));

    if (studyData instanceof osparc.data.model.Study) {
      this.__study = studyData;
    } else {
      this.__study = new osparc.data.model.Study(studyData);
    }

    this.__populateLayout(maxHeight);
  },

  members: {
    __study: null,

    __populateLayout: function(maxHeight) {
      const hBox = new qx.ui.container.Composite(new qx.ui.layout.HBox(8));
      const vBox = new qx.ui.container.Composite(new qx.ui.layout.VBox(8));
      vBox.add(this.__createTitle());
      vBox.add(this.__createExtraInfo());
      hBox.add(vBox);
      hBox.add(this.__createThumbnail(maxHeight), {
        flex: 1
      });
      this._add(hBox);
      this._add(this.__createDescription());
    },

    __createThumbnail: function(maxHeight) {
      const image = new qx.ui.basic.Image().set({
        scale: true,
        allowStretchX: true,
        allowStretchY: true,
        maxHeight: maxHeight ? parseInt(maxHeight) : 200
      });

      this.__study.bind("thumbnail", image, "source");
      this.__study.bind("thumbnail", image, "visibility", {
        converter: thumbnail => {
          if (thumbnail) {
            return "visible";
          }
          return "excluded";
        }
      });

      return image;
    },

    __createExtraInfo: function() {
      const grid = new qx.ui.layout.Grid(5, 3);
      grid.setColumnAlign(0, "right", "middle");
      grid.setColumnAlign(1, "left", "middle");
      grid.setColumnFlex(0, 1);
      grid.setColumnFlex(1, 1);
      const moreInfo = new qx.ui.container.Composite(grid).set({
        maxWidth: 220,
        alignY: "middle"
      });

      const creationDate = new qx.ui.basic.Label();
      const lastChangeDate = new qx.ui.basic.Label();
      const owner = new qx.ui.basic.Label();

      // create a date format like "Oct. 19, 2018 11:31 AM"
      const dateFormat = new qx.util.format.DateFormat(
        qx.locale.Date.getDateFormat("medium") + " " +
        qx.locale.Date.getTimeFormat("short")
      );
      const dateOptions = {
        converter: date => dateFormat.format(date)
      };
      this.__study.bind("creationDate", creationDate, "value", dateOptions);
      this.__study.bind("lastChangeDate", lastChangeDate, "value", dateOptions);
      this.__study.bind("prjOwner", owner, "value");

      moreInfo.add(new qx.ui.basic.Label(this.tr("Owner")).set({
        font: "title-12"
      }), {
        row: 0,
        column: 0
      });
      moreInfo.add(owner, {
        row: 0,
        column: 1
      });
      moreInfo.add(new qx.ui.basic.Label(this.tr("Creation date")).set({
        font: "title-12"
      }), {
        row: 1,
        column: 0
      });
      moreInfo.add(creationDate, {
        row: 1,
        column: 1
      });
      moreInfo.add(new qx.ui.basic.Label(this.tr("Last modified")).set({
        font: "title-12"
      }), {
        row: 2,
        column: 0
      });
      moreInfo.add(lastChangeDate, {
        row: 2,
        column: 1
      });

      return moreInfo;
    },

    __createTitle: function() {
      const title = new qx.ui.basic.Label().set({
        font: "nav-bar-label",
        allowStretchX: true,
        rich: true
      });

      this.__study.bind("name", title, "value");

      return title;
    },

    __createDescription: function() {
      const description = new osparc.ui.markdown.Markdown();
      this.__study.bind("description", description, "markdown");
      return description;
    }
  }
});
