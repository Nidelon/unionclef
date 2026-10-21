package kaptainwutax.tungsten.agent;

import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.phys.shapes.CollisionContext;
import net.minecraft.core.BlockPos;
import net.minecraft.world.phys.Vec3;
import net.minecraft.world.phys.shapes.VoxelShape;
import net.minecraft.world.level.BlockGetter;
import net.minecraft.world.level.ClipContext;

public class AgentRaycastContext extends ClipContext {

	private final net.minecraft.world.level.ClipContext.Block shapeType;
	private final AgentShapeContext shapeContext;

	public AgentRaycastContext(Vec3 start, Vec3 end, net.minecraft.world.level.ClipContext.Block shapeType, net.minecraft.world.level.ClipContext.Fluid fluidHandling, Agent agent) {
		super(start, end, shapeType, fluidHandling, CollisionContext.empty());
		this.shapeType = shapeType;
		this.shapeContext = new AgentShapeContext(agent);
	}

	@Override
	public VoxelShape getBlockShape(BlockState state, BlockGetter world, BlockPos pos) {
		return this.shapeType.get(state, world, pos, this.shapeContext);
	}

}
