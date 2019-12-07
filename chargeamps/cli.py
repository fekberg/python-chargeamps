"""ChargeAmps Client"""

import argparse
import asyncio
import json
import logging
import sys

from aiohttp.client_exceptions import ClientResponseError

from .base import ChargeAmpsClient
from .external import ChargeAmpsExternalClient

logger = logging.getLogger(__name__)


async def get_chargepoint_id(client: ChargeAmpsClient, args: argparse.Namespace) -> str:
    if args.charge_point_id:
        return args.charge_point_id
    chargepoints = await client.get_chargepoints()
    return chargepoints[0].id


async def command_list_chargepoints(client: ChargeAmpsClient, args: argparse.Namespace):
    res = []
    for cp in await client.get_chargepoints():
        res.append(cp.to_dict())
    print(json.dumps(res, indent=4))


async def command_get_chargepoint_status(client: ChargeAmpsClient, args: argparse.Namespace):
    charge_point_id = await get_chargepoint_id(client, args)
    cp = await client.get_chargepoint_status(charge_point_id)
    if args.connector_id:
        for c in cp.connector_statuses:
            if c.connector_id == args.connector_id:
                print(json.dumps(c.to_dict(), indent=4))
    else:
        print(json.dumps(cp.to_dict(), indent=4))


async def command_get_chargepoint_sessions(client: ChargeAmpsClient, args: argparse.Namespace):
    charge_point_id = await get_chargepoint_id(client, args)
    for session in await client.get_chargingsessions(charge_point_id):
        if args.connector_id is None or args.connector_id == session.connector_id:
            print(json.dumps(session.to_dict(), indent=4))


async def command_get_chargepoint_settings(client: ChargeAmpsClient, args: argparse.Namespace):
    charge_point_id = await get_chargepoint_id(client, args)
    if args.connector_id:
        connector_ids = [args.connector_id]
    else:
        cp = await client.get_chargepoint_status(charge_point_id)
        connector_ids = [c.connector_id for c in cp.connector_statuses]
    res = []
    for connector_id in connector_ids:
        settings = await client.get_chargepoint_connector_settings(charge_point_id, connector_id)
        res.append(settings.to_dict())
    print(json.dumps(res, indent=4))


async def command_set_chargepoint_settings(client: ChargeAmpsClient, args: argparse.Namespace):
    charge_point_id = await get_chargepoint_id(client, args)
    connector_id = args.connector_id
    settings = await client.get_chargepoint_connector_settings(charge_point_id, connector_id)
    if args.max_current:
        settings.max_current = args.max_current
    if args.enable:
        settings.mode = "On"
    elif args.disable:
        settings.mode = "Off"
    await client.set_chargepoint_connector_settings(settings)


def add_arg_chargepoint(parser, required=False):
    parser.add_argument('--chargepoint',
                        dest='charge_point_id',
                        metavar='ID',
                        type=str,
                        required=required,
                        help="ChargePoint ID")


def add_arg_connector(parser, required=False):
    parser.add_argument('--connector',
                        dest='connector_id',
                        metavar='ID',
                        type=int,
                        required=required,
                        help="Connector ID")


async def main_loop() -> None:
    """Main function"""

    parser = argparse.ArgumentParser(description='Chargeamps Client')
    parser.add_argument('--config',
                        metavar='config',
                        required=True,
                        help='Config file')
    parser.add_argument('--debug',
                        action='store_true',
                        help="Enable debugging")

    subparsers = parser.add_subparsers(dest='command')

    parser_list = subparsers.add_parser('chargepoints', help="List all chargepoints")
    parser_list.set_defaults(func=command_list_chargepoints)

    parser_status = subparsers.add_parser('status', help="Get chargepoint status")
    parser_status.set_defaults(func=command_get_chargepoint_status)
    add_arg_chargepoint(parser_status)
    add_arg_connector(parser_status)

    parser_sessions = subparsers.add_parser('sessions', help="Get chargepoint sessions")
    parser_sessions.set_defaults(func=command_get_chargepoint_sessions)
    add_arg_chargepoint(parser_sessions)
    add_arg_connector(parser_sessions)

    parser_get = subparsers.add_parser('get', help="Get chargepoint settings")
    parser_get.set_defaults(func=command_get_chargepoint_settings)
    add_arg_chargepoint(parser_get)
    add_arg_connector(parser_get)

    parser_set = subparsers.add_parser('set', help="Change chargepoint settings")
    parser_set.set_defaults(func=command_set_chargepoint_settings)
    add_arg_chargepoint(parser_set)
    add_arg_connector(parser_set, required=True)
    parser_set.add_argument('--enable',
                            dest='enable',
                            action='store_true',
                            help="Enable connector")
    parser_set.add_argument('--disable',
                            dest='disable',
                            action='store_true',
                            help="Disable connector")
    parser_set.add_argument('--current',
                            dest='max_current',
                            metavar='amps',
                            type=int,
                            required=False,
                            help="Max current")

    args = parser.parse_args()

    if args.debug:
        logging.basicConfig(level=logging.DEBUG)

    with open(args.config) as config_file:
        config = json.load(config_file)

    client = ChargeAmpsExternalClient(email=config['username'],
                                      password=config['password'],
                                      api_key=config['api_key'])

    try:
        await args.func(client, args)
    except ClientResponseError as exc:
        sys.stderr.write(str(exc))
    except ValueError as exc:
        if args.debug:
            raise exc
        parser.print_help()
        await client.shutdown()
        sys.exit(0)

    await client.shutdown()


def main() -> None:
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(main_loop())
    finally:
        loop.close()


if __name__ == "__main__":
    main()