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


qx.Class.define("osparc.info.StudyUtils", {
  type: "static",

  statics: {
    /**
      * @param study {osparc.data.model.Study} Study Model
      */
    createTitle: function(study) {
      const title = osparc.info.Utils.createTitle();
      study.bind("name", title, "value");
      return title;
    },

    /**
      * @param study {osparc.data.model.Study} Study Model
      */
    createUuid: function(study) {
      const uuid = osparc.info.Utils.createId();
      study.bind("uuid", uuid, "value");
      study.bind("uuid", uuid, "toolTipText");
      return uuid;
    },

    /**
      * @param study {osparc.data.model.Study} Study Model
      */
    createOwner: function(study) {
      const owner = new qx.ui.basic.Label();
      study.bind("prjOwner", owner, "value", {
        converter: email => {
          if (email === osparc.auth.Data.getInstance().getEmail()) {
            return qx.locale.Manager.tr("me");
          }
          return osparc.utils.Utils.getNameFromEmail(email);
        },
        onUpdate: (source, target) => {
          target.setToolTipText(source.getPrjOwner());
        }
      });
      return owner;
    },

    /**
      * @param study {osparc.data.model.Study} Study Model
      */
    createCreationDate: function(study) {
      const creationDate = new qx.ui.basic.Label();
      study.bind("creationDate", creationDate, "value", {
        converter: date => osparc.utils.Utils.formatDateAndTime(date)
      });
      return creationDate;
    },

    /**
      * @param study {osparc.data.model.Study} Study Model
      */
    createLastChangeDate: function(study) {
      const lastChangeDate = new qx.ui.basic.Label();
      study.bind("lastChangeDate", lastChangeDate, "value", {
        converter: date => osparc.utils.Utils.formatDateAndTime(date)
      });
      return lastChangeDate;
    },

    /**
      * @param study {osparc.data.model.Study} Study Model
      */
    createAccessRights: function(study) {
      const accessRights = new qx.ui.basic.Label();
      let permissions = "";
      const myGID = osparc.auth.Data.getInstance().getGroupId();
      const ar = study.getAccessRights();
      if (myGID in ar) {
        if (ar[myGID]["delete"]) {
          permissions = qx.locale.Manager.tr("Owner");
        } else if (ar[myGID]["write"]) {
          permissions = qx.locale.Manager.tr("Collaborator");
        } else if (ar[myGID]["read"]) {
          permissions = qx.locale.Manager.tr("Viewer");
        }
      }
      accessRights.setValue(permissions);
      return accessRights;
    },

    /**
      * @param study {osparc.data.model.Study} Study Model
      */
    createClassifiers: function(study) {
      const nClassifiers = new qx.ui.basic.Label();
      study.bind("classifiers", nClassifiers, "value", {
        converter: classifiers => `(${classifiers.length})`
      });
      return nClassifiers;
    },

    /**
      * @param study {osparc.data.model.Study} Study Model
      */
    createQuality: function(study) {
      const tsrLayout = new qx.ui.container.Composite(new qx.ui.layout.HBox(2)).set({
        toolTipText: qx.locale.Manager.tr("Ten Simple Rules score")
      });
      const addStars = model => {
        tsrLayout.removeAll();
        const quality = model.getQuality();
        if (osparc.component.metadata.Quality.isEnabled(quality)) {
          const tsrRating = new osparc.ui.basic.StarsRating();
          tsrRating.set({
            nStars: 4,
            showScore: true
          });
          osparc.ui.basic.StarsRating.scoreToStarsRating(quality["tsr_current"], quality["tsr_target"], tsrRating);
          tsrLayout.add(tsrRating);
        } else {
          tsrLayout.exclude();
        }
      };
      study.addListener("changeQuality", () => addStars(study), this);
      addStars(study);
      return tsrLayout;
    },

    /**
      * @param study {osparc.data.model.Study} Study Model
      * @param maxWidth {Number} thumbnail's maxWidth
      * @param maxHeight {Number} thumbnail's maxHeight
      */
    createThumbnail: function(study, maxWidth, maxHeight) {
      const thumbnail = osparc.info.Utils.createThumbnail(maxWidth, maxHeight);
      const noThumbnail = "osparc/no_photography_black_24dp.svg";
      study.bind("thumbnail", thumbnail, "source", {
        converter: thumb => thumb ? thumb : noThumbnail,
        onUpdate: (source, target) => {
          if (source.getThumbnail() === "") {
            target.getChildControl("image").set({
              minWidth: 100,
              minHeight: 100
            });
          }
        }
      });
      return thumbnail;
    },

    /**
      * @param study {osparc.data.model.Study} Study Model
      * @param maxHeight {Number} description's maxHeight
      */
    createDescriptionMD: function(study, maxHeight) {
      const description = new osparc.ui.markdown.Markdown().set({
        noMargin: true
      });
      if (maxHeight) {
        description.setMaxHeight(maxHeight);
      }
      study.bind("description", description, "value", {
        converter: desc => desc ? desc : "Add description"
      });
      return description;
    },

    /**
      * @param study {osparc.data.model.Study} Study Model
      */
    createDisableServiceAutoStart: function(study) {
      const cb = new qx.ui.form.CheckBox().set({
        label: qx.locale.Manager.tr("Disable Services Auto Start"),
        toolTipText: qx.locale.Manager.tr("This will help opening and closing studies faster"),
        iconPosition: "right"
      });
      const devObj = study.getDev();
      cb.setValue(("disableServiceAutoStart" in devObj) ? devObj["disableServiceAutoStart"] : false);
      cb.addListener("changeValue", e => {
        const newVal = e.getData();
        devObj["disableServiceAutoStart"] = newVal;
        study.updateStudy({
          dev: devObj
        });
      });
      return cb;
    },

    /**
      * @param study {osparc.data.model.Study} Study Model
      */
    createTags: function(study) {
      const tagsContainer = new qx.ui.container.Composite(new qx.ui.layout.HBox(5));

      const addTags = model => {
        tagsContainer.removeAll();
        const noTagsLabel = new qx.ui.basic.Label(qx.locale.Manager.tr("Add tags"));
        tagsContainer.add(noTagsLabel);
        osparc.store.Store.getInstance().getTags().filter(tag => model.getTags().includes(tag.id))
          .forEach(selectedTag => {
            if (tagsContainer.indexOf(noTagsLabel) > -1) {
              tagsContainer.remove(noTagsLabel);
            }
            tagsContainer.add(new osparc.ui.basic.Tag(selectedTag.name, selectedTag.color));
          });
      };
      study.addListener("changeTags", () => addTags(study), this);
      addTags(study);

      return tagsContainer;
    },

    createExtraInfoVBox: function(extraInfos) {
      const grid = new qx.ui.layout.Grid(10, 8);
      grid.setColumnAlign(0, "right", "middle");
      grid.setColumnAlign(1, "left", "middle");
      const moreInfo = new qx.ui.container.Composite(grid);

      Object.keys(extraInfos).forEach((key, idx) => {
        const extraInfo = extraInfos[key];

        const title = new qx.ui.basic.Label(extraInfo.label);
        moreInfo.add(title, {
          row: idx,
          column: 0
        });

        moreInfo.add(extraInfo.view, {
          row: idx,
          column: 1
        });
      });

      return moreInfo;
    },

    titleWithEditLayout: function(data) {
      const titleLayout = new qx.ui.container.Composite(new qx.ui.layout.HBox(5));
      const title = new qx.ui.basic.Label(data.label);
      titleLayout.add(title);
      if (data.action) {
        titleLayout.add(data.action.button);
        data.action.button.addListener("execute", () => {
          const cb = data.action.callback;
          if (typeof cb === "string") {
            data.action.ctx.fireEvent(cb);
          } else {
            cb.call(data.action.ctx);
          }
        }, this);
      }
      return titleLayout;
    },

    createExtraInfoGrid: function(extraInfos) {
      const positions = {
        THUMBNAIL: {
          column: 0,
          row: 0*3
        },
        CREATED: {
          column: 0,
          row: 1*3
        },
        MODIFIED: {
          column: 0,
          row: 2*3
        },
        ACCESS_RIGHTS: {
          column: 0,
          row: 3*3
        },
        AUTHOR: {
          column: 0,
          row: 4*3
        },
        TAGS: {
          column: 0,
          row: 5*3
        },
        QUALITY: {
          column: 0,
          row: 6*3
        },
        CLASSIFIERS: {
          column: 0,
          row: 7*3
        }
      };

      const grid = new qx.ui.layout.Grid(40, 5);
      grid.setColumnAlign(0, "left", "middle");
      grid.setColumnAlign(1, "left", "middle");
      grid.setColumnAlign(2, "left", "middle");
      grid.setColumnAlign(3, "left", "middle");
      grid.setRowHeight(1*3-1, 10); // spacer
      grid.setRowHeight(2*3-1, 10); // spacer
      grid.setRowHeight(3*3-1, 10); // spacer
      grid.setRowHeight(4*3-1, 10); // spacer
      grid.setRowHeight(5*3-1, 10); // spacer
      grid.setRowHeight(6*3-1, 10); // spacer
      grid.setRowHeight(7*3-1, 10); // spacer
      const moreInfo = new qx.ui.container.Composite(grid);

      Object.keys(positions).forEach(key => {
        if (key in extraInfos) {
          const extraInfo = extraInfos[key];
          const gridInfo = positions[key];

          const titleLayout = this.titleWithEditLayout(extraInfo);
          moreInfo.add(titleLayout, {
            row: gridInfo.row,
            column: gridInfo.column,
            colSpan: gridInfo.colSpan ? gridInfo.colSpan : 1
          });

          moreInfo.add(extraInfo.view, {
            row: gridInfo.row+1,
            column: gridInfo.column,
            colSpan: gridInfo.colSpan ? gridInfo.colSpan : 1,
            rowSpan: gridInfo.rowSpan ? gridInfo.rowSpan : 1
          });
        }
      });

      return moreInfo;
    },

    /**
      * @param studyData {Object} Serialized Study Object
      */
    openAccessRights: function(studyData) {
      const permissionsView = new osparc.component.share.CollaboratorsStudy(studyData);
      const title = qx.locale.Manager.tr("Share with Collaborators and Organizations");
      osparc.ui.window.Window.popUpInWindow(permissionsView, title, 500, 400);
      return permissionsView;
    },

    /**
      * @param resourceData {Object} Serialized Resource Object
      */
    openQuality: function(resourceData) {
      const qualityEditor = new osparc.component.metadata.QualityEditor(resourceData);
      const title = resourceData["name"] + " - " + qx.locale.Manager.tr("Quality Assessment");
      osparc.ui.window.Window.popUpInWindow(qualityEditor, title, 650, 700);
      return qualityEditor;
    }
  }
});
