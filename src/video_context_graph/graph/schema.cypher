CREATE CONSTRAINT video_id_unique IF NOT EXISTS
FOR (v:Video) REQUIRE v.video_id IS UNIQUE;

CREATE CONSTRAINT scene_id_unique IF NOT EXISTS
FOR (s:Scene) REQUIRE s.scene_id IS UNIQUE;

CREATE CONSTRAINT entity_id_unique IF NOT EXISTS
FOR (e:Entity) REQUIRE e.entity_id IS UNIQUE;

CREATE CONSTRAINT event_id_unique IF NOT EXISTS
FOR (e:Event) REQUIRE e.event_id IS UNIQUE;

CREATE CONSTRAINT tag_id_unique IF NOT EXISTS
FOR (t:Tag) REQUIRE t.tag_id IS UNIQUE;

CREATE INDEX entity_lookup IF NOT EXISTS
FOR (e:Entity) ON (e.video_id, e.normalized_name, e.entity_type);

CREATE INDEX scene_time_lookup IF NOT EXISTS
FOR (s:Scene) ON (s.video_id, s.start_sec);

CREATE INDEX event_time_lookup IF NOT EXISTS
FOR (e:Event) ON (e.video_id, e.start_sec);

CREATE INDEX video_collection_lookup IF NOT EXISTS
FOR (v:Video) ON (v.store_id, v.recorded_at);

CREATE INDEX video_camera_lookup IF NOT EXISTS
FOR (v:Video) ON (v.store_id, v.camera_id);
