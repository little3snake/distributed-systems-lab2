import argparse
from contextlib import nullcontext
import threading
import time

from flask import Flask, jsonify, request


app = Flask(__name__)

potions = {}
next_potion_id = 1
potions_lock = threading.Lock()
use_lock = True
race_delay_seconds = 0.0


def storage_guard():
    #return the real lock in safe mode and an empty context in unsafe mode
    return potions_lock if use_lock else nullcontext()


@app.errorhandler(404)
def handle_route_not_found(_error):
    return jsonify({"error": "Route not found"}), 404


@app.errorhandler(405)
def handle_method_not_allowed(_error):
    return jsonify({"error": "Method not allowed"}), 405


@app.get("/potions")
def list_potions():
    with storage_guard():
        result = list(potions.values())
    return jsonify(result), 200


@app.get("/potions/<int:potion_id>")
def get_potion(potion_id):
    with storage_guard():
        potion = potions.get(potion_id)

    if potion is None:
        return jsonify({"error": "Potion not found"}), 404
    return jsonify(potion), 200


@app.post("/potions")
def create_potion():
    global next_potion_id

    if not request.is_json:
        return jsonify({"error": "Content-Type must be application/json"}), 415

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "Request body must be a JSON object"}), 400

    name = data.get("name")
    effect = data.get("effect")
    ingredients = data.get("ingredients")

    if not isinstance(name, str) or not name.strip():
        return jsonify({"error": "Field 'name' must be a non-empty string"}), 400
    if not isinstance(effect, str) or not effect.strip():
        return jsonify({"error": "Field 'effect' must be a non-empty string"}), 400
    if (
        not isinstance(ingredients, list)
        or not ingredients
        or not all(isinstance(item, str) and item.strip() for item in ingredients)
    ):
        return jsonify({"error": "Field 'ingredients' must be a non-empty list of strings"}), 400

    normalized_name = name.strip()

    with storage_guard():
        if any(
            existing_potion["name"].casefold() == normalized_name.casefold()
            for existing_potion in potions.values()
        ):
            return jsonify({"error": "Potion with this name already exists"}), 409

        # reading and updating next_potion_id is one critical operation. In
        # unsafe mode other request threads can read the same value here.
        potion_id = next_potion_id
        if race_delay_seconds > 0:
            time.sleep(race_delay_seconds)

        potion = {
            "id": potion_id,
            "name": normalized_name,
            "effect": effect.strip(),
            "ingredients": [item.strip() for item in ingredients],
        }
        potions[potion_id] = potion
        next_potion_id = potion_id + 1

    return jsonify(potion), 201


@app.delete("/potions/<int:potion_id>")
def delete_potion(potion_id):
    with storage_guard():
        potion = potions.pop(potion_id, None)

    if potion is None:
        return jsonify({"error": "Potion not found"}), 404
    return jsonify(potion), 200


def parse_arguments():
    parser = argparse.ArgumentParser(description="Lab 2 Potions REST API")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5000)
    parser.add_argument(
        "--lock-mode",
        choices=("locked", "unsafe"),
        default="locked",
        help="Protect shared potion storage with Lock or demonstrate a race",
    )
    parser.add_argument(
        "--race-delay",
        type=float,
        default=0.0,
        help="Delay inside id generation used to make the race visible",
    )
    return parser.parse_args()


def main():
    global use_lock, race_delay_seconds

    args = parse_arguments()
    if not 1 <= args.port <= 65535:
        raise SystemExit("Port must be between 1 and 65535")

    if args.race_delay < 0:
        raise SystemExit("Race delay must be zero or greater")

    use_lock = args.lock_mode == "locked"
    race_delay_seconds = args.race_delay
    print(f"Storage mode: {args.lock_mode}; race delay: {race_delay_seconds:.4f}s", flush=True,)
    app.run(host=args.host, port=args.port, debug=False, threaded=True)


if __name__ == "__main__":
    main()
