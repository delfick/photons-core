import { takeEvery, select, takeLatest, put } from "redux-saga/effects";
import { createAction, createReducer } from "redux-act";

import { WSState, WSCommand } from "./wsclient.js";

var combine_tiles = (tiles, existing) => {
  var by_key = {};
  existing.map(tile => {
    by_key[tile.key] = tile;
  });

  var result = [];
  var anyDifferent = false;

  tiles.map(tile => {
    if (!by_key[tile.key]) {
      by_key[tile.key] = {};
    }

    var nxt = { ...by_key[tile.key], ...tile };

    var different = false;
    Object.keys(nxt).map(attr => {
      if (by_key[tile.key][attr] != nxt[attr]) {
        different = true;
      }
    });

    if (different) {
      result.push(nxt);
      anyDifferent = true;
    } else {
      result.push(by_key[tile.key]);
    }
  });

  if (anyDifferent) {
    return result;
  } else {
    return existing;
  }
};

class TilesStateKls {
  Error = createAction(
    "Failed to interact with the server",
    ({ namespace, error, error_code, reason, original }) => {
      if (!reason) {
        reason = original.type.substr(original.type.indexOf("] ") + 2);
        if (original.reason) {
          reason = original.reason;
        }
      }

      reason = `${error_code}: Failure while ${reason}`;

      if (typeof error !== "string" && !(error instanceof String)) {
        error = JSON.stringify(error);
      }

      return { namespace, reason, error, original };
    }
  );

  ClearError = createAction("Clear error");

  MakeStream = createAction("Make a stream");
  StartedStream = createAction("Started a stream", messageId => ({
    messageId
  }));
  LoadingStream = createAction("Loading a stream");
  StreamProgress = createAction("Progress from a stream");

  Highlight = createAction("highlight a tile", (serial, tile_index) => ({
    serial,
    tile_index
  }));

  GotTiles = createAction("Got tiles");
  ChangeCoords = createAction("Change coords");

  reducer() {
    return createReducer(
      {
        [this.Error]: (state, error) => {
          return { ...state, error };
        },
        [this.ClearError]: (state, _) => {
          return { ...state, error: undefined };
        },
        [this.StartedStream]: (state, { messageId }) => {
          return { ...state, loading: false, messageId };
        },
        [WSState.Error]: (state, _) => {
          return { ...state, loading: false, tiles: [] };
        },
        [this.LoadingStream]: (state, _) => {
          return {
            ...state,
            loading: true,
            error: undefined,
            tiles: [],
            messageId: undefined
          };
        },
        [this.GotTiles]: (state, tiles) => {
          return {
            ...state,
            tiles: combine_tiles(tiles, state.tiles),
            waiting: false
          };
        }
      },
      {
        tiles: [],
        error: undefined,
        waiting: true,
        loading: false,
        messageId: undefined
      }
    );
  }
}

export const TileState = new TilesStateKls();

function* wsConnectedSaga() {
  yield put(TileState.MakeStream());
}

function* changeCoordsSaga(original) {
  let messageId = yield select(state => state.tiles.messageId);
  if (!messageId) {
    return;
  }

  yield put(
    WSCommand(
      "/v1/lifx/command",
      {
        command: "change_coords",
        args: original.payload
      },
      { onerror: TileState.Error, original, parentMessageIds: [messageId] }
    )
  );
}

function* highlightSaga(original) {
  let messageId = yield select(state => state.tiles.messageId);
  if (!messageId) {
    return;
  }

  yield put(
    WSCommand(
      "/v1/lifx/command",
      {
        command: "highlight",
        args: original.payload
      },
      { onerror: TileState.Error, original, parentMessageIds: [messageId] }
    )
  );
}

function* makeTileStreamSaga(original) {
  let loading = yield select(state => state.tiles.loading);
  if (loading) {
    return;
  }

  let onsuccess = TileState.LoadingStream;
  let onerror = TileState.Error;
  let onprogress = TileState.StreamProgress;

  yield put(TileState.LoadingStream());

  yield put(
    WSCommand(
      "/v1/lifx/command",
      {
        command: "tiles/store"
      },
      { onsuccess, onprogress, onerror, original }
    )
  );
}

function* streamProgressSaga(command) {
  let { payload } = command;

  if (payload.progress.error) {
    yield put(
      TileState.Error({
        ...payload.progress,
        original: { type: "[] processing device discovery" }
      })
    );
    return;
  }

  let instruction = payload.progress.instruction;

  if (instruction == "started") {
    yield put(TileState.StartedStream(payload.messageId));
  } else if (instruction == "tiles") {
    yield put(TileState.GotTiles(payload.progress.tiles));
  }
}

export function* tilesSaga() {
  yield takeEvery(TileState.StreamProgress, streamProgressSaga);
  yield takeEvery(TileState.Highlight, highlightSaga);
  yield takeEvery(TileState.ChangeCoords, changeCoordsSaga);

  yield takeLatest(TileState.MakeStream, makeTileStreamSaga);
  yield takeLatest(WSState.Connected, wsConnectedSaga);
}
