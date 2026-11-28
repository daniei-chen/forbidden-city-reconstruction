"""Cache only rendered gate-route geometry for repeated physical ray probes."""
from mathutils import Vector
from mathutils.bvhtree import BVHTree


def trees(scene, graph):
    result = []
    for obj in scene.objects:
        if obj.type != 'MESH' or not obj.data.polygons or obj.hide_render:
            continue
        evaluated = obj.evaluated_get(graph)
        matrix = evaluated.matrix_world.copy()
        corners = [matrix @ Vector(point) for point in obj.bound_box]
        low = [min(p[k] for p in corners) for k in range(3)]
        high = [max(p[k] for p in corners) for k in range(3)]
        if (high[0] < -59 or low[0] > 55 or high[1] < -508 or low[1] > -444
                or high[2] < -.35 or low[2] > 8.5):
            continue
        tree = BVHTree.FromObject(obj, graph)
        if tree is not None:
            result.append((obj, tree, matrix, matrix.inverted_safe()))
    if not result:
        raise RuntimeError('No rendered gate-route collision surfaces were found.')
    return result


def ray(cached, origin, direction, distance):
    origin, direction = Vector(origin), Vector(direction).normalized()
    closest = distance + 1.e-6
    found = (False, None, None, -1, None, None)
    for obj, tree, matrix, inverse in cached:
        local = inverse @ origin
        target = inverse @ (origin + direction * closest)
        delta = target - local
        if delta.length < 1.e-8:
            continue
        hit, normal, index, _ = tree.ray_cast(local, delta.normalized(), delta.length)
        if hit is None:
            continue
        position = matrix @ hit
        actual_distance = (position - origin).length
        if actual_distance < closest:
            closest = actual_distance
            found = (True, position, matrix.to_3x3() @ normal, index, obj, matrix)
    return found


def foot(cached, x, y):
    # The path centre can coincide with a real 5 mm grout joint. Stand on the
    # highest supporting point within a small shoe footprint, not the joint.
    hits = [ray(cached, (x + dx, y + dy, 1.2), (0, 0, -1), 3.)
            for dx, dy in ((0., 0.), (-.08, 0.), (.08, 0.), (0., -.10), (0., .10))]
    supporting = [hit for hit in hits if hit[0]]
    return max(supporting, key=lambda hit: hit[1].z) if supporting else hits[0]
