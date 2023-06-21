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
      * @param study {osparc.data.model.Study|Object} Study or Serialized Study Object
      */
    createTitle: function(study) {
      const title = osparc.info.Utils.createTitle();
      if (study instanceof osparc.data.model.Study) {
        study.bind("name", title, "value");
      } else {
        title.setValue(study["name"]);
      }
      return title;
    },

    /**
      * @param study {osparc.data.model.Study|Object} Study or Serialized Study Object
      */
    createUuid: function(study) {
      const uuid = osparc.info.Utils.createId();
      if (study instanceof osparc.data.model.Study) {
        study.bind("uuid", uuid, "value");
        study.bind("uuid", uuid, "toolTipText");
      } else {
        uuid.set({
          value: study["uuid"],
          toolTipText: study["uuid"]
        });
      }
      return uuid;
    },

    /**
      * @param study {osparc.data.model.Study|Object} Study or Serialized Study Object
      */
    createOwner: function(study) {
      const owner = new qx.ui.basic.Label();
      if (study instanceof osparc.data.model.Study) {
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
      } else {
        owner.set({
          value: osparc.utils.Utils.getNameFromEmail(study["prjOwner"]),
          toolTipText: study["prjOwner"]
        });
      }
      return owner;
    },

    /**
      * @param study {osparc.data.model.Study|Object} Study or Serialized Study Object
      */
    createCreationDate: function(study) {
      const creationDate = new qx.ui.basic.Label();
      if (study instanceof osparc.data.model.Study) {
        const dateOptions = {
          converter: date => osparc.utils.Utils.formatDateAndTime(date)
        };
        study.bind("creationDate", creationDate, "value", dateOptions);
      } else {
        const date = osparc.utils.Utils.formatDateAndTime(new Date(study["creationDate"]));
        creationDate.setValue(date);
      }
      return creationDate;
    },

    /**
      * @param study {osparc.data.model.Study|Object} Study or Serialized Study Object
      */
    createLastChangeDate: function(study) {
      const lastChangeDate = new qx.ui.basic.Label();
      if (study instanceof osparc.data.model.Study) {
        const dateOptions = {
          converter: date => osparc.utils.Utils.formatDateAndTime(date)
        };
        study.bind("lastChangeDate", lastChangeDate, "value", dateOptions);
      } else {
        const date = osparc.utils.Utils.formatDateAndTime(new Date(study["lastChangeDate"]));
        lastChangeDate.setValue(date);
      }
      return lastChangeDate;
    },

    /**
      * @param study {osparc.data.model.Study|Object} Study or Serialized Study Object
      */
    createAccessRights: function(study) {
      let permissions = "";
      const myGID = osparc.auth.Data.getInstance().getGroupId();
      const ar = (study instanceof osparc.data.model.Study) ? study.getAccessRights() : study["accessRights"];
      if (myGID in ar) {
        if (ar[myGID]["delete"]) {
          permissions = qx.locale.Manager.tr("Owner");
        } else if (ar[myGID]["write"]) {
          permissions = qx.locale.Manager.tr("Collaborator");
        } else if (ar[myGID]["read"]) {
          permissions = qx.locale.Manager.tr("Viewer");
        }
      }
      const accessRights = new qx.ui.basic.Label(permissions);
      return accessRights;
    },

    /**
      * @param study {osparc.data.model.Study|Object} Study or Serialized Study Object
      */
    createClassifiers: function(study) {
      const nClassifiers = new qx.ui.basic.Label();
      if (study instanceof osparc.data.model.Study) {
        study.bind("classifiers", nClassifiers, "value", {
          converter: classifiers => `(${classifiers.length})`
        });
      } else {
        nClassifiers.setValue(`(${study["classifiers"].length})`);
      }
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
      * @param study {osparc.data.model.Study|Object} Study or Serialized Study Object
      * @param maxWidth {Number} thumbnail's maxWidth
      * @param maxHeight {Number} thumbnail's maxHeight
      */
    createThumbnail: function(study, maxWidth, maxHeight) {
      const thumbnail = osparc.info.Utils.createThumbnail(maxWidth, maxHeight);
      const noThumbnail = "osparc/no_photography_black_24dp.svg";
      if (study instanceof osparc.data.model.Study) {
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
      } else if (study["thumbnail"]) {
        thumbnail.set({
          source: study["thumbnail"]
        });
      } else {
        thumbnail.set({
          source: noThumbnail,
          minWidth: 100,
          minHeight: 100
        });
      }
      return thumbnail;
    },

    /**
      * @param study {osparc.data.model.Study|Object} Study or Serialized Study Object
      * @param maxHeight {Number} description's maxHeight
      */
    createDescription: function(study, maxHeight) {
      const description = new osparc.ui.markdown.Markdown().set({
        noMargin: true,
        maxHeight: maxHeight
      });
      if (study instanceof osparc.data.model.Study) {
        study.bind("description", description, "value", {
          converter: desc => desc ? desc : "Add description"
        });
      } else {
        description.setValue(study["description"] ? study["description"] : "Add description");
      }
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
            tagsContainer.remove(noTagsLabel);
            tagsContainer.add(new osparc.ui.basic.Tag(selectedTag.name, selectedTag.color));
          });
      };
      study.addListener("changeTags", () => addTags(study), this);
      addTags(study);

      return tagsContainer;
    },

    createExtraInfo: function(extraInfos) {
      const positions = {
        DESCRIPTION: {
          column: 0,
          row: 0,
          colSpan: 3
        },
        THUMBNAIL: {
          column: 3,
          row: 0
        },
        ACCESS_RIGHTS: {
          column: 0,
          row: 3
        },
        AUTHOR: {
          column: 1,
          row: 3
        },
        CREATED: {
          column: 2,
          row: 3
        },
        MODIFIED: {
          column: 3,
          row: 3
        },
        TAGS: {
          column: 0,
          row: 6,
          colSpan: 2
        },
        QUALITY: {
          column: 2,
          row: 6
        },
        CLASSIFIERS: {
          column: 3,
          row: 6
        }
      };

      const grid = new qx.ui.layout.Grid(40, 5);
      grid.setColumnAlign(0, "left", "middle");
      grid.setColumnAlign(1, "left", "middle");
      grid.setColumnAlign(2, "left", "middle");
      grid.setColumnAlign(3, "left", "middle");
      grid.setRowHeight(2, 10); // spacer
      grid.setRowHeight(5, 10); // spacer
      const moreInfo = new qx.ui.container.Composite(grid);

      Object.keys(positions).forEach(key => {
        if (key in extraInfos) {
          const extraInfo = extraInfos[key];
          const gridInfo = positions[key];

          const titleLayout = new qx.ui.container.Composite(new qx.ui.layout.HBox(5));
          const title = new qx.ui.basic.Label(extraInfo.label);
          titleLayout.add(title);
          if (extraInfo.action) {
            titleLayout.add(extraInfo.action.button);
            extraInfo.action.button.addListener("execute", () => {
              const cb = extraInfo.action.callback;
              if (typeof cb === "string") {
                extraInfo.action.ctx.fireEvent(cb);
              } else {
                cb.call(extraInfo.action.ctx);
              }
            }, this);
          }
          moreInfo.add(titleLayout, {
            row: gridInfo.row,
            column: gridInfo.column,
            colSpan: gridInfo.colSpan ? gridInfo.colSpan : 1
          });

          moreInfo.add(extraInfo.view, {
            row: gridInfo.row+1,
            column: gridInfo.column,
            colSpan: gridInfo.colSpan ? gridInfo.colSpan : 1
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
